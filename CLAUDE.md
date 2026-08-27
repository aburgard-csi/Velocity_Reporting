# Retail Performance Engine — Deck Build Router

This project builds client Executive Review decks for three programs. Each program has
its own subagent and its own data sources. **Keep them separate** — never run one
program's logic while building another. Confusion between programs is the exact problem
this structure exists to prevent.

## Routing

Identify the program from the request, then dispatch to the one matching subagent:

| Ask mentions… | Program | Subagent |
| --- | --- | --- |
| ARS, Account Revenue Solution, mailings, Lift Matrix, Reg E, debit take rate | ARS | `ars-deck` |
| ICS, Invitation Checking, referrals, mystery shop, ROI per account | ICS | `ics-deck` |
| MRPC, MyRewards Premium Cards, enrollments, Gold/Platinum tiers | MRPC | `mrpc-deck` |

If a request names a client but not a program, ask which program before building. If it
asks for a combined ARS+ICS+MRPC review (like the Marine reference deck), run each
subagent in turn and assemble with `build/assemble_combined.py` (see **Combined decks**) —
do not improvise one blended path.

## File locations (this machine has no Google Drive — confirmed local folders)

This copy of the project runs on a machine without Google Drive access. Aaron confirmed the
local folders below on **2026-07-15**; use them for every build. Do not hardcode any *other*
path or invent a Drive id. If Aaron says a folder has moved, or a build's inputs aren't where
the table says, ask him to point at the specific file rather than guessing — but do not
re-ask the whole walk-through each session.

**Source data** — the workbook and ODD folders were moved OFF OneDrive to a plain local
drive to stop sync corruption/lock issues (Aaron, **2026-07-17**). Both now live under
`C:\Data Pipelines\RPE Pipeline\Inputs\`:

| Input | Folder |
| --- | --- |
| Raw ODDD extracts (zipped, `<id>_ODDD.zip`) | `C:\Data Pipelines\RPE Pipeline\Inputs\ODDD\` |
| ARS, MRPC, **and ICS** workbooks (all together) | `C:\Data Pipelines\RPE Pipeline\Inputs\ARS & MRPC Reports\` |
| Reference deck (Marine 1539) | the project `templates\` folder |

**Output — ONE destination (Aaron, 2026-07-25).** Save every finished deck to
**Pipeline Outputs** only — `C:\Data Pipelines\RPE Pipeline\Outputs\` (flat; program is
distinguished by the filename tag, not by subfolder). This replaces both the old
**Client Presentations** drop and the per-client `Clients\<Client Name> <clientid>\<PROGRAM>
Delivery\` copy — do not deliver to client folders going forward. In Cowork the mounted
folders are typically the pipeline `Inputs\ODDD`, `Inputs\ARS & MRPC Reports`, and
`Outputs` (all under `C:\Data Pipelines\RPE Pipeline\`). **Write hazard:** these mounts allow creating/copying files but NOT deleting —
`rm` returns "Operation not permitted." Copy-to-deliver works; if a file must be replaced or
removed, ask Aaron to do it. Confirm the writable target per session.

If Aaron has instead re-authorized the Google Drive **connector** for this machine, he may
tell you to use Drive over the connector rather than a local folder — in that case use the
connector for reads/writes. Default to the local folders above unless he says otherwise.

## Shared conventions (all programs)

**Output — one destination.** Every finished deck is saved to the pipeline `Outputs\`
folder only (see **File locations** above). Program is distinguished by the filename tag,
not by subfolder. No per-client Delivery copies (Aaron, 2026-07-25).

**Decks ship as `.pptx` only — do not generate a PDF** (Aaron, 2026-07-24). PDF is not part
of the pipeline; do not add a LibreOffice/`soffice` conversion step or deliver a `.pdf`
alongside the deck.

**Combined decks — the standard for multi-product clients (Aaron, 2026-08-27).** A client on
more than one program gets ONE combined ARS+ICS+MRPC Executive Review, not three separate
decks. Build each program's deck first (each must pass its own validation gate), then
assemble:

```
python3 build/assemble_combined.py <ars.pptx> <ics.pptx> <mrpc.pptx> <out.pptx>
```

The result is the 79-slide structure of `templates/multi-product_reference_deck.pptx`: shared
shell (1-3), ARS (4-30), ICS (31-53), MRPC (54-62), Questions + Contact (63-64), ARS Appendix
(65-79). Each program deck's own title / Summit / agenda / Q&A / Contact slides are dropped so
the combined deck carries exactly one of each; the title slide lists all three products and the
agenda names the three sections. Slides are only ever ADDED and then reordered — never deleted
— because freeing a slide partname makes python-pptx hand that number to a later slide and the
package ends up referencing parts twice (the defect behind the unopenable 2026.08 ICS decks).
Run `validation/qa_all.py` on the assembled deck: it checks package integrity and that the file
actually opens, which a 0-FAIL lint pass alone does not.

**A combined deck is not always three fresh builds.** ICS financials are quarterly, so between
workbooks the ICS section carries the previous workbook's figures forward unchanged (see
**Cadence**). The ICS section may therefore report an older month than the ARS and MRPC
sections. That is expected — do not "align" it, re-date it, or zero it. The per-slide source
notes name the workbook and its period, which is what keeps a carried-forward figure auditable.
`assemble_combined.py` prints each section's period so the difference is visible at build time.

**Filename convention:**

```
<clientid>-<yyyy.mm>-<PROGRAM>-<Client Name> <PROGRAM> Results.pptx
```

- `<PROGRAM>` is one of `ARS`, `ICS`, `MRPC`, or `ARS-ICS-MRPC` for a combined deck.
- `<yyyy.mm>` is the data/period month, e.g. `2026.07`.
- Examples: `1539-2026.07-ARS-Marine FCU ARS Results.pptx`,
  `1539-2026.07-ICS-Marine FCU ICS Results.pptx`,
  `1539-2026.07-MRPC-Marine FCU MRPC Results.pptx`,
  `1075-2026.08-ARS-ICS-MRPC-Austin Bank Results.pptx` (combined; Aaron 2026-08-27).

**Templates.** Each program clones-and-swaps from the latest Marine FCU (1539) reference
deck, using that program's section only. See `templates/TEMPLATES.md` for the reference
deck's filename and exact section slide ranges. The reference deck is a source input —
locate it under the source-data location Aaron provides (see **File locations**), not a
Drive id.

**Build machinery.** The deck-assembly code lives in `build/`, one folder per program
(reorganized 2026-07-24): `build/ars_pipeline/` (the full ARS chain — `build_ars_gen.py`
plus `metrics_gen`, `charts_gen`, `extract_base_gen`, `extract_lift`, `render_lift`,
`ticket_calc`, `ticket_chart`, `base_tab_extract`, `product_mix_slide`), `build/ics_pipeline/`,
`build/mrpc_pipeline/`. Shared post-processors sit in `build/` root (`restyle_fonts.py`, `summit_slide.py`,
`fit_layout.py` — layout-fit + 10pt slide numbers, run by all builders before save) and `build/strip_dead.py`. The ODD
optimizer is `scripts/oddd_optimize.py`; the validator is `validation/validate_deck.py`.
Superseded one-offs, the deprecated pre-`build_ars_gen` ARS recipe (`build_gen`/`build_gen_b`/
`build_swipepct`/`style_tables`/`swap_imgs`), backups (`*_orig`), and the old combined-Marine
helpers were moved to `archive/` (see `archive/MANIFEST.md`) — do not call anything under
`archive/`. See `build/README.md`. Requires python-pptx, matplotlib, openpyxl, Pillow.

**Validation gate.** Run `validation/validate_deck.py` on every built deck before it
ships. A non-zero exit blocks delivery — fix and re-run, do not override.

**QA gate — run after ANY change to `templates/`, `build/`, or `validation/` (2026-07-24):**

```
python3 validation/qa_all.py [built_deck.pptx ...]        # gate: validates every template + given decks
python3 validation/qa_all.py --snapshot ...               # accept INTENTIONAL layout changes as the new baseline
python3 validation/qa_all.py --no-render ...              # skip the render smoke test (faster; use sparingly)
```

**Standing rule (Aaron, 2026-08-17): when a defect gets through the gate, add the check
that would have caught it.** Fixing only the instance guarantees the next one ships too.

It runs the full validator on every template (banned words, counts, glyph-aware collisions,
caption overflow, PowerPoint autofit shrink, chart-vs-tile rail) AND compares each slide's
layout fingerprint against `validation/layout_baseline.json` — **DRIFT warnings mean a shared
pass touched slides you didn't intend to change** (the class of regression that otherwise
only a human spots). Review drifts, then `--snapshot` to accept. It also runs an **OOXML
package-integrity check** and a **render smoke test** (opens each deck in LibreOffice and
compares the PDF page count to the slide count). Three hard-won rules:
1. **LibreOffice renders are not PowerPoint.** `normAutofit` font-scaling is invisible in
   soffice renders — the validator FAILs any frame with fontScale <90%; never trust nominal
   font sizes on template-inherited frames.
2. **Box geometry is not glyph geometry.** Text overflows its box silently; the validator
   estimates rendered glyph runs (font-size- and alignment-aware). When adding layout rules,
   fix the BUILDER/geometry contract (slide_geometry.py, fit_layout.py) — never hand-edit
   one deck.
3. **python-pptx is not the file.** Every text/geometry rule reads the deck *through*
   python-pptx, which enumerates a duplicated slide reference as two real slides. All seven
   2026.08 ICS decks passed at 0 FAIL while being unopenable in LibreOffice (50 parts, 28
   references, six parts referenced twice). Package integrity and "does it actually open"
   are now checked directly — added 2026-08-17 after that shipped.

**Swap gate — a text swap that matches nothing FAILS the build (2026-07-25).** The ARS
builder records every find-string that matched no shape and exits non-zero listing them. This
exists because a silent no-op is the worst failure mode in this pipeline: the slide keeps the
TEMPLATE's numbers and ships looking perfectly plausible. It is how the entire Appendix and the
"Profit This Month" tile carried the reference client's figures into every deck until
2026-07-25. Related rule: **resolve slides by TITLE, never by index** — `build_ars_gen.SB(title)`
raises if the title is absent, whereas `S[n]` silently points at the wrong slide the moment the
template gains or loses one.

**Missing source data is stated, never zeroed.** If a field the deck needs is absent from the
extract (e.g. an all-blank `DOB` column → no age profile), the builder writes a plain sentence
saying the data isn't carried in this extract and flags it — it does not render a 0% or an
empty chart, and it does not drop the slide.

**Never drop slides automatically.** The deck keeps its full slide set. If a section's
data looks absent in one source — e.g. Reg E not present in the ODD dump — that is a
data-sourcing task, not a reason to remove the slide: populate it from the correct
source (workbook / core / VIP) or flag it for Aaron. Do not silently omit slides and do
not report a phantom 0%.

**Data sources in slide notes — always.** Every slide must list its data source(s) in the
slide's speaker notes: the source file(s) or dashboard (ODD extract + pull date, workbook
tab, VIP dashboard, ICS Charts, MRPCPM Analysis, etc.) and the selection/period behind the
numbers. No slide ships without a source line in its notes. This is a hard requirement, not
a nicety — it is what makes a figure auditable back to its origin.

The source strings in the notes must name **the client being built** — its own client id,
name, ODD extract + pull stamp, and workbook filename — never the reference/template
client. The builders derive these per-client from the data pack (`oddd_metrics.json`
`source_file`/`latest_month`, plus the client id and name); do not hardcode them. This is a
real defect that has shipped before: `build/ars_pipeline/build_ars_gen.py` defaulted its
`ODD_SRC`/`WB_SRC` to CoastLife 1705, so every client's deck inherited CoastLife source
notes (fixed 2026-07-24 — now derived, with env overrides `ARS_ODD_SRC` / `ARS_WB_SRC` /
`ARS_WB_FILE`). **Verify every build:** grep the finished deck's notes for the reference
client (e.g. "CoastLife", "1705") — zero hits required — and confirm the notes carry the
correct client id, pull stamp, workbook name, and MM-vs-SM tab wording before delivery.

**Standardized category values (every build, every client).** These mappings apply to all
programs and all clients without exception. Normalize these fields to one fixed vocabulary
so every build reads the same — never invent a mapping:

- **Reg E opt-in status** → `Reg E Opt In`, `Reg E Opt Out`, `Reg E Default`.
- **Account status** → `Open`, `Closed`, `Dormant`, `Inactive`, `Frozen`, `Charged Off`, `Other`.
  Core lifecycle wording confirmed by Aaron (2026-07-25), now in the shared classifier:
  `Purge at Yearend` → **Closed**, `Pending Closeout` → **Closed**, `New This Cycle` → **Open**,
  `Pending Activation` → **Open**, `Manually controlled` → **Other** (deliberate — it no longer
  surfaces as unmapped).

`oddd_optimize.py` applies these (`classify_rege` / `classify_status`). Blank Reg E cells are
excluded (closed/business — not applicable); blank/unknown statuses fall to `Other`. Any
non-blank value that doesn't map is surfaced in the pack's `flags` block — **ask Aaron how to
map it before building; do not guess.**

**Visual style guide.** All decks (every product) follow `templates/STYLE.md` — fonts
(Montserrat headings / Calibri detail, both embedded), title-slide rules (list only the
included products; reporting month = generation month), callout/tile style (drop shadows on
all callouts and on pie/donut charts), table format, chart standards, selection-on-slide /
source-in-notes, and page renumbering. **Read `templates/STYLE.md` before building any deck,
and keep it as the single source of truth for visual style across ARS / ICS / MRPC.**

**Writing style.** All client-facing text follows Aaron's rules (Obsidian
`Claude/Operating Instructions.md`). Banned words include: robust, comprehensive,
leverage, seamless, delve, and the banker-deck list — engine, lever, lift (as prose;
"ARS Lift Matrix" as a proper slide name is fine), ramping, healthy, predominantly,
companion, seasoned book, annuity. No superlatives or unsupported higher/lower claims.

## Cadence

| Program | When | Scope |
| --- | --- | --- |
| ARS | Monthly | Every ARS client, each month — MM or SM path per client |
| MRPC | Monthly | Every MRPC client, each month |
| ICS | Quarterly full refresh; optional monthly referral update | Financials refresh only when a new ICS workbook lands (quarterly). Referrals come from VIP and can be updated monthly — a monthly build carries the latest workbook's financial sections forward in the client JSON unchanged (source notes keep the workbook period, so carried-forward figures stay auditable). Missing-section guard in the builder stops any build whose data sheet has never been populated. |

## Data sources by program (do not cross these)

All inputs live under the **source-data location** Aaron names at the start of the session
(see **File locations**). The folder names below (`Workbooks - ARS`, `Workbooks - ICS`) are
the expected layout inside that location — if Aaron's local copy is organized differently,
ask him to point at the specific file rather than guessing.

- **ARS** — raw ODD via the `oddd-optimizer` subagent (run it first), plus the ARS
  workbook (Lift Matrix MM tab / `base_extract.json`). ODD-driven.
- **ICS** — ICS Workbook (ROI, lifetime value, revenue, financial summary), VIP ICS
  Referral dashboard (referral counts/trend/branch), ICS Charts 2026 (mystery shops).
  Not ODD-driven; `oddd-optimizer` is not used.
- **MRPC** — VIP MyRewards Premium Cards dashboards + the MRPC workbook (MRPCPM
  Analysis) for enrollments, channel mix, retention, revenue. Not ODD-driven. The
  `...-MRPCPM_Analysis_v10.xlsx` files live in the shared **Workbooks - ARS** folder
  (no separate MRPC folder). ICS workbooks + Charts live in **Workbooks - ICS**.

## Project file map (keep current)

This is the readme index — update it whenever files are added, removed, or moved.

**Root**
- `CLAUDE.md` — this file: routing, shared conventions, and this file map.
- `VIP Navigation Guide.md` — how to pull ICS/MRPC data from the VIP dashboards.
- `ARS Build Package.zip` — exportable snapshot of the ARS pipeline (regenerated from live).

**`scripts/`**
- `oddd_optimize.py` — raw ODD → data pack (`oddd_pack.md` + `oddd_metrics.json`); Reg E / account-status classifiers, funnel, mix.

**`build/ars_pipeline/` — the ARS pipeline (client-agnostic)**
- `build_ars_gen.py` — the ARS deck assembler: clones the template, swaps content, inserts Product Mix, writes source notes, adds the Contact slide, moves the Appendix after Contact, restyles fonts, runs the logo/slide-number branding pass.
- `metrics_gen.py` — ~105 chart metrics from the ODD (streams the `.zip`).
- `charts_gen.py` — renders the 28 chart PNGs; `DIM` = each chart's pixel size (must match its slide box aspect).
- `chart_lib.py` — shared take-rate-by-branch renderer (personal orange / business navy; identical size).
- `base_tab_extract.py` — SM financials from the workbook (+ DCO).
- `extract_base_gen.py` / `extract_lift.py` — MM financials / Lift Matrix rows.
- `render_lift.py`, `ticket_calc.py`, `ticket_chart.py` — Lift Matrix chart (MM); average-ticket calc + chart.
- `product_mix_slide.py` — builds the Product Mix & ARS Eligibility slide from the ODD.

**`build/` (shared)**
- `restyle_fonts.py` — font-role post-processor, run last on every deck (all programs).
- `strip_dead.py` — zip-level dead-slide GC (called by the ARS assembler).
- `summit_slide.py` — inserts the Executive Summit slide (used by ICS/MRPC).
- `assemble_combined.py` — builds the combined ARS+ICS+MRPC deck from the three finished
  program decks (see **Combined decks** above).
- `rpe_env.py` — machine-local paths (`RPE_DATA_ROOT` → `inputs()` / `outputs()`) and
  `use_font()`, which registers the bundled fonts and RAISES instead of letting matplotlib
  substitute a missing face. Every chart renderer goes through it.
- `assets/` — `logo.png` (CSI|Velocity lockup), `csi_logo.png`, `summit_slide.pptx`, `Velocity Executive Summit.jpg`.
- `README.md` — build/ layout notes (incl. the SM-vs-MM revenue-model extractor notes).

**`build/ics_pipeline/`** — ICS pipeline: `build_ics_gen.py`, `ics_charts_gen.py`, `data/` (per-client VIP ICS data — one folder per client; keep client-named).
**`build/mrpc_pipeline/`** — MRPC pipeline: `build_mrpc_gen.py`, `mrpc_charts_gen.py`, `setup_template.py` (one-time template bootstrap), `data/` (per-client VIP MRPC data).

**`templates/`** — ALL deck templates live here (consistent naming; passed to each builder as an arg).
- `ars_template.pptx`, `ics_template.pptx`, `mrpc_template.pptx` — the three stripped per-program shells the builders clone (cleaned + styled; "Union Financial" dummy client).
- `mrpc_template_base.pptx` — 9-slide base that `setup_template.py` bootstraps `mrpc_template.pptx` from.
- `multi-product_reference_deck.pptx` — combined ARS+ICS+MRPC reference (Union Financial demo, styled); source for re-materializing the stripped templates.
- `STYLE.md` — visual style guide (single source of truth). `TEMPLATES.md` — reference section map + template materialization.


**`validation/`** — `validate_deck.py`: pre-ship lint gate (0 FAIL to ship).
**`dashboards/`** — `RPE Dashboard.html` (delivery tracker) and `RPE Performance.html` (per-client KPIs); also maintained as Claude artifacts.
**`fonts/Montserrat/`** — Montserrat family (TTFs) embedded in decks; Carlito (charts) ships with the environment.
**`archive/`** — retired code, stale client caches, and historical docs (`RUNBOOK.md`, PRD) under `archive/historical/` (`archive/MANIFEST.md`); nothing live references it.
