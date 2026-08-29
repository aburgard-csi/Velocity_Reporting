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
asks for a combined ARS+ICS+MRPC review, run each subagent in turn and assemble with
`build/assemble_combined.py` (see **Combined decks**) — do not improvise one blended path,
and do not start from an existing combined deck.

## File locations

Paths are resolved from **`RPE_DATA_ROOT`** (`build/rpe_env.py` → `inputs()` / `outputs()`),
set per machine in `.env`. Never hardcode a path or a Drive id in code — if a build's inputs
aren't where `RPE_DATA_ROOT` says, ask Aaron to point at the specific file rather than
guessing, but do not re-ask the whole walk-through each session.

**This Mac has Google Drive mounted** (corrected 2026-08-28 — this section previously said it
did not, and named `C:\Data Pipelines\...` as the only source. Both `~/My Drive/...` and the
`.env` value below resolve today):

```
RPE_DATA_ROOT=~/Library/CloudStorage/GoogleDrive-<account>/My Drive/Work/RPE Pipeline
```

| Input | Folder under `RPE_DATA_ROOT` |
| --- | --- |
| Raw ODDD extracts (zipped, `<id>_ODDD.zip`) | `Inputs/ODDD/` |
| ARS, MRPC, **and ICS** workbooks (all together) | `Inputs/ARS & MRPC Reports/` |
| Client logos (`<clientid>.png`) | `Inputs/Logos/` |
| ICS / MRPC client sheets from the VIP dashboards | `Inputs/VIP Data/<PROGRAM>/<id>-<Name>/<id>_<program>.json` |
| Build evidence (figure sidecars) — NOT deliverables | `Build Artifacts/` |
| Per-program template shells (`*_template.pptx`) | the project `templates/` folder |

**VIP Data.** `Inputs/VIP Data/` holds the per-client ICS and MRPC sheets pulled from the
VIP dashboards, one folder per client (`<PROGRAM>/<id>-<Name>/`), indexed by
`manifest.json` (program, client id, period, pull date, sections). Resolve one with
`rpe_env.resolve_client_json("1705", "ics")` — it takes a bare client id and prefers the
manifest. **This is the only source.** `build/{ics,mrpc}_pipeline/data/` used to hold
copies and was deleted 2026-08-29: the store carried 2026-08-29 pulls while the repo still
had 2026-08-10, and a build reading the repo shipped month-old figures that validated
perfectly because they were internally consistent. Two stores for one fact is the problem.
See the folder's own `README.md` for provenance, currency and the refresh procedure.

**Client logos** live in `Inputs/Logos/<clientid>.png` — NOT in the repo: a client's logo is
their brand asset and nothing client-identifiable belongs in git. `rpe_env.client_logo(id)`
resolves it (png → jpg → extensionless, each opened before use) and returns `None` when
absent, so a missing logo never fails a build. `rpe_env.trim_logo()` crops to the ink before
placement — the files carry white OR transparent padding (1549 is a 2940x1532 canvas with the
mark in one corner), and fitting the raw canvas renders a right-sized box holding a tiny logo.
`rpe_env.fit_box()` preserves aspect: these run 1.50 to 8.77 wide-to-tall, so a fixed width
stretches one client and overflows another.

**`Outputs/` holds finished decks and nothing else (Aaron, 2026-08-29).** Anything a build
emits to prove itself — the figure provenance sidecar, the `.A/.B/.C/.D` phase decks — goes
to `Build Artifacts/` or is cleaned up. `rpe_env.build_artifacts()` resolves that folder and
creates it on demand; unlike `inputs()`/`outputs()` it never raises, because a build must not
die for want of somewhere to put its bookkeeping.

**Output — ONE destination (Aaron, 2026-07-25).** Every finished deck goes to `Outputs/`
(flat; program is distinguished by the filename tag, not by subfolder). This replaced both
the old **Client Presentations** drop and the per-client `Clients/<Client Name> <clientid>/`
copy — do not deliver to client folders.

**On the CSI/Cowork machine** the same tree is mounted from a plain local drive at
`C:\Data Pipelines\RPE Pipeline\` (moved off OneDrive to stop sync corruption — Aaron
2026-07-17), with `Inputs\ODDD`, `Inputs\ARS & MRPC Reports`, and `Outputs` under it. Set
`RPE_DATA_ROOT` to that root there. **Write hazard on those mounts:** they allow creating and
copying files but NOT deleting — `rm` returns "Operation not permitted". Copy-to-deliver
works; if a file must be replaced or removed, ask Aaron. Confirm the writable target per
session.

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
python3 build/assemble_combined.py --ars <ars.pptx> [--ics <ics.pptx>] [--mrpc <mrpc.pptx>] \
                                   --out <out.pptx>
```

`--ars` is required — the ARS deck supplies the shared shell, Questions/Contact and the
Appendix. `--ics` / `--mrpc` are optional, so the same tool builds a two-program deck:
**most multi-product clients are on two programs, not three** (2026.08: five ARS+ICS, one
ARS+MRPC, two all-three). The title slide lists only the included products and the agenda
only the included sections — an unused agenda row is REMOVED, not blanked, because an empty
numbered row reads as a section that failed to render.

All three programs gives the 79-slide structure of
`templates/multi-product_reference_deck.pptx`: shared shell (1-3), ARS (4-30), ICS (31-53),
MRPC (54-62), Questions + Contact (63-64), ARS Appendix (65-79). ARS+ICS drops the MRPC
section for 70 slides; ARS+MRPC drops the ICS section. Each program deck's own title / Summit / agenda / Q&A / Contact slides are dropped so
the combined deck carries exactly one of each; the title slide lists all three products and the
agenda names the three sections. Slides are only ever ADDED and then reordered — never deleted
— because freeing a slide partname makes python-pptx hand that number to a later slide and the
package ends up referencing parts twice (the defect behind the unopenable 2026.08 ICS decks).
Run `validation/qa_all.py` on the assembled deck: it checks package integrity and that the file
actually opens, which a 0-FAIL lint pass alone does not.

**The ICS section presents current results only (Aaron, 2026-08-28).** ICS financials are
quarterly, and a monthly build used to carry the previous workbook's figures forward. It no
longer does: **if there is no workbook for the deck's own period, the workbook-driven ICS
elements are not included at all.** The builder resolves the newest ICS workbook for the client
from `Inputs/ARS & MRPC Reports/` and compares its period to the deck's; on a mismatch the ICS
section falls back to the referrals-only shape — Referrals, Referral Trend, Results by Branch
and the education slides — and the divider drops to "Referrals".

Do not carry an older workbook's figures forward, and do not re-date, align or zero them. An
ICS section that reports an older month than ARS and MRPC is no longer an expected outcome; it
is a defect. The fix is a current workbook, not a carried-forward number.
`assemble_combined.py` prints each section's period so any divergence is visible at build time.

**Filename convention:**

```
<clientid>-<yyyy.mm>-<PROGRAM>-<Client Name> <PROGRAM> Results.pptx
```

- `<PROGRAM>` is one of `ARS`, `ICS`, `MRPC`, or `ARS-ICS-MRPC` for a combined deck.
- `<yyyy.mm>` is the data/period month, e.g. `2026.07`.
- Examples: `1204-2026.08-ARS-FSB Michigan ARS Results.pptx`,
  `1705-2026.08-ICS-CoastLife Credit Union ICS Results.pptx`,
  `1075-2026.08-ARS-ICS-MRPC-Austin Bank Results.pptx` (combined; Aaron 2026-08-27).

**Templates — build from the shell, never from a client deck (Aaron, 2026-08-29).** Each
program is BUILT by its builder from the stripped per-program template in the repo's
`templates/` folder — `ars_template.pptx`, `ics_template.pptx`, `mrpc_template.pptx` — each
a cleaned, styled shell carrying the "Union Financial" dummy client and no real client's
numbers. The builder takes that shell as its first argument and populates every slide from
the data pack.

**No deck is ever cloned from another client's finished deck.** The older recipe cloned the
latest Marine FCU (1539) results deck and swapped its content; that is retired. Cloning a
client deck carries that client's numbers, captions, branch names and speaker notes into the
next client's file, and every one of those has leaked in practice — it is the mechanism
behind the reference-leak rule below and behind `validate_deck.py`'s
`reference_leak_findings`. A figure that was never swapped is indistinguishable from one
that was, which is why the gate has to hunt for them at all.

If a slide is wrong, fix the BUILDER and the template shell, then rebuild. Do not hand-edit
a deck and do not reach for a previous client's file as a starting point.

`templates/TEMPLATES.md` records each shell's slide inventory and per-slide swap targets.
`multi-product_reference_deck.pptx` (Union Financial demo) is the source for
re-materializing the shells — it is a STYLING reference, not a build input.

**Build machinery.** The deck-assembly code lives in `build/`, one folder per program
(reorganized 2026-07-24): `build/ars_pipeline/` (the full ARS chain — `build_ars_gen.py`
plus `metrics_gen`, `charts_gen`, `extract_base_gen`, `extract_lift`, `render_lift`,
`ticket_calc`, `ticket_chart`, `base_tab_extract`, `product_mix_slide`), `build/ics_pipeline/`,
`build/mrpc_pipeline/`.

**Shared layer in `build/` root — used by ALL THREE programs (Aaron, 2026-08-29).** Anything
that is not specific to one program lives here, not inside a pipeline folder:
`brand.py` (the palette and type roles — the ONE source; it was previously re-declared in
seven files under four naming conventions, and the greys had already drifted),
`shapes.py` (the slide primitives — textbox, pill, tile, add_table, fit_picture,
blank_slide, move_before, renumber; these used to live inside `product_mix_slide.py`, a
module about one slide, where ICS and MRPC could not reach them),
`periods.py` (every derived date phrase — windows, spans, month counts; a literal month is
fine when it IS the month being described, but never hand-derive a span or a count),
`slide_geometry.py` (the per-title geometry contract, promoted out of `ars_pipeline/` so
all three programs can adopt it), plus the post-processors `restyle_fonts.py`,
`summit_slide.py`, `fit_layout.py` (layout-fit + 10pt slide numbers, run by all builders
before save), `strip_dead.py`, `textfit.py`, `branch_names.py` and `assemble_combined.py`.
ARS-specific shared code stays in `build/ars_pipeline/` — `odd_rows.py` (the ODD row
vocabulary: `g`, `fnum`, `swipes`, `spend`, `personal`, `hascard`, `isopen`) is there
because the ODD is an ARS input.

The ODD optimizer is `scripts/oddd_optimize.py`; the validator is `validation/validate_deck.py`.
Superseded one-offs, the deprecated pre-`build_ars_gen` ARS recipe (`build_gen`/`build_gen_b`/
`build_swipepct`/`style_tables`/`swap_imgs`), backups (`*_orig`), and the old combined-Marine
helpers were left OUT of this repo (they remain in the Drive copy's `archive/`) — nothing here
imports them, and nothing should. See `build/README.md`. Requires python-pptx, matplotlib, openpyxl, Pillow.

**Validation gate.** Run `validation/validate_deck.py <deck> [base.json]` on every built
deck before it ships. A non-zero exit blocks delivery — fix and re-run, do not override.
Passing `base.json` switches on the data-vs-deck cross-check; `validation/qa_all.py` finds
it automatically when it sits beside the deck, or takes `--extract`.

**Unit suite.** `pytest tests/` — classifiers, the ODD row vocabulary, metrics invariants,
the palette, the period derivations, the deck rules and `assemble_combined`. It runs as
step 0 of `qa_all.py` and a failure fails the gate, because a classifier regression that
mis-buckets 18,000 accounts still produces a deck that passes every layout rule. The
fixture is a synthetic 800-row ODD (`tests/fixtures/make_odd.py`) carrying no real member
data. Skip with `--no-tests` only when you know why.

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
compares the PDF page count to the slide count). The render test needs `soffice` on PATH;
without it the gate now says so **loudly**, per deck and in a summary banner (2026-08-27 — it
used to be silent on skip *and* on success, so a machine with no LibreOffice reported a clean
gate while the one check that proves a deck opens had never run). Three hard-won rules:
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

- **Status CODE fallback** (Aaron, 2026-08-28) — not every core populates `Stat Desc`.
  1549 Wellworth fills `Stat Code` and leaves `Stat Desc` BLANK on every non-open account
  (18,274 of 50,218 rows). `oddd_optimize.STAT_CODE_MAP` is the one place that mapping
  lives: **`O`/`A` → Open, `C` → Closed, `X` → Charged Off**. The description still wins
  whenever it carries text; the code is consulted only when it is blank.

`oddd_optimize.py` applies these (`classify_rege` / `classify_status`). Blank Reg E cells are
excluded (closed/business — not applicable); a blank status with no usable `Stat Code` falls
to `Other`. Any non-blank value that doesn't map — description OR code — is surfaced in the
pack's `flags` block — **ask Aaron how to map it before building; do not guess.**

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
| ICS | Quarterly full refresh; monthly referral update | Referrals come from VIP monthly. **Financial detail ships ONLY when the ICS workbook is for the deck's own period (Aaron, 2026-08-28).** This REPLACES the previous carry-forward rule: a monthly build used to carry the last workbook's financial sections forward, which kept them auditable in the source notes but dated them as current on the slide face — 1537 and 1676 both stamped "PTD · August 2026" on figures from 2026.06 and 2026.07 workbooks. The builder now resolves the newest ICS workbook for the client from `Inputs/ARS & MRPC Reports/` and, if its period differs from the deck's, omits the workbook-driven sections entirely. Referrals, Referral Trend, Results by Branch and the education slides are unaffected. Missing-section guard still stops a build whose data sheet was never populated. |

**ICS before the first workbook — referrals-only builds (Aaron, 2026-08-27).** A client can be
live on ICS and generating referrals before their first ICS workbook ever lands (Wellworth 1549).
Their VIP referral data is real and worth showing, so build the ICS deck with:

```
python3 build/ics_pipeline/build_ics_gen.py --referrals-only <client_ics.json> \
        templates/ics_template.pptx <out.pptx>
```

This keeps the referral slides (Power of Referrals, Referral Trend, Results by Branch) plus the
education/reference and Q&A slides, and **omits** the workbook-driven slides (account
performance, revenue, financial summary, comparisons) entirely — they are absent, never
rendered from null or shown as 0. The section divider drops to "Referrals" so the deck does not
advertise sections it lacks. It is **opt-in only**: without the flag the missing-section guard
still stops the build, so a client whose data sheet was simply never populated cannot silently
ship a short section. Combined decks handle the shorter section automatically — `assemble_combined.py`
selects a program's slides by exclusion, not by fixed index.

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
- `clients.md` — **which clients get which programs.** Program membership is recorded
  here, NOT inferred from whether an input file exists: CoastLife 1705 kept producing an
  ICS section after cancelling because their ICS data was still on disk. Check it before
  building, and update it when a program starts or stops.
- `CHANGELOG.md` — behavior changes that move a client-facing number or its source.
- `requirements.txt`, `.env.example` — runtime deps; `RPE_DATA_ROOT` and friends.
- `docs/` — `PRD-2026-08-26-repo-portability-and-response-rates.md`.

**`scripts/`**
- `oddd_optimize.py` — raw ODD → data pack (`oddd_pack.md` + `oddd_metrics.json`); Reg E / account-status classifiers, funnel, mix.

**`build/ars_pipeline/` — the ARS pipeline (client-agnostic)**
- `build_ars_gen.py` — the ARS deck assembler: populates the `ars_template.pptx` shell, inserts Product Mix and Excluded Accounts, writes source notes, adds the Contact slide, moves the Appendix after Contact, restyles fonts, runs the logo/slide-number branding pass.
- `metrics_gen.py` — ~105 chart metrics from the ODD (streams the `.zip`).
- `charts_gen.py` — renders the 28 chart PNGs; `DIM` = each chart's pixel size (must match its slide box aspect).
- `chart_lib.py` — shared take-rate-by-branch renderer (personal orange / business navy; identical size).
- `base_tab_extract.py` — SM financials from the workbook (+ DCO).
- `extract_base_gen.py` / `extract_lift.py` — MM financials / Lift Matrix rows.
- `render_lift.py`, `ticket_calc.py`, `ticket_chart.py` — Lift Matrix chart (MM); average-ticket calc + chart.
- `product_mix_slide.py` — builds the Product Mix & ARS Eligibility slide from the ODD.
- `rege_branch_slide.py` — builds the Reg E Opt-In by Branch table slide (the table
  companion to the two Reg E branch charts): opted in / opted out / no election per
  branch, sized to the space on the slide. Tiles read the SAME population as the table.
- `excluded_accounts_slide.py` — builds the Excluded Accounts slide that follows it: the
  eligibility waterfall (status → product code → debit card, each account counted once) and
  the per-client excluded product codes, derived as those with no eligible account. $0
  balance and address quality are reported as observations, NOT as exclusions — neither
  predicts the `Elig` flag (see the module docstring for the evidence).
- `slide_geometry.py` — the builder/geometry contract layout rules are fixed in (CLAUDE.md rule 2).

*Standalone ARS tools — run by hand, not part of the deck chain:*
- `build_ars_onepager.py` — the 8.5x11 print one-pager. Deliberately skips
  restyle_fonts / fit_layout / validate_deck, which enforce the 13.33x7.5 deck contract.
- `responder_activity.py` — responder before/after activity from the raw ODD; feeds the one-pager.
- `lift_extract.py` → `build_lift_matrix.py` — per-account ODD extract (`.pkl`) and the
  standalone ARS Lift Matrix workbook built from it (the file sent to Bradford).

**`build/` (shared)**
- `restyle_fonts.py` — font-role post-processor, run last on every deck (all programs).
- `strip_dead.py` — zip-level dead-slide GC (called by the ARS assembler).
- `summit_slide.py` — inserts the Executive Summit slide (used by ICS/MRPC).
- `assemble_combined.py` — builds the combined ARS+ICS+MRPC deck from the three finished
  program decks (see **Combined decks** above).
- `fit_layout.py` — layout-fit pass + 10pt slide numbers; run by every builder before save.
- `textfit.py` — measures rendered glyph width against the bundled TTFs (`fits_one_line`);
  used by the ICS builder and the validator. Never eyeball whether a label fits.
- `branch_names.py` — branch id → name lookup shared by the ARS chart renderers.
- `rpe_env.py` — machine-local paths (`RPE_DATA_ROOT` → `inputs()` / `outputs()`) and
  `use_font()`, which registers the bundled fonts and RAISES instead of letting matplotlib
  substitute a missing face. Every chart renderer goes through it.
- `assets/` — `logo.png` (CSI|Velocity lockup), `csi_logo.png`, `summit_slide.pptx`, `Velocity Executive Summit.jpg`.
- `README.md` — build/ layout notes (incl. the SM-vs-MM revenue-model extractor notes).

**`build/ics_pipeline/`** — ICS pipeline: `build_ics_gen.py`, `ics_charts_gen.py`,
`ics_workbook_extract.py` (the quarterly step: populates a client JSON's workbook sections
from the ICS workbook — see **Cadence**), `data/` (per-client VIP ICS data — one folder per client; keep client-named).
**`build/mrpc_pipeline/`** — MRPC pipeline: `build_mrpc_gen.py`, `mrpc_charts_gen.py`, `setup_template.py` (one-time template bootstrap; needs `mrpc_template_base.pptx`, which is NOT in the repo — ask Aaron for it if the template must be rebuilt), `data/` (per-client VIP MRPC data).

**`templates/`** — ALL deck templates live here (consistent naming; passed to each builder as an arg).
- `ars_template.pptx`, `ics_template.pptx`, `mrpc_template.pptx` — the three stripped per-program shells the builders populate (cleaned + styled; "Union Financial" dummy client). **The only legitimate starting point for a build.**
- `multi-product_reference_deck.pptx` — combined ARS+ICS+MRPC reference (Union Financial demo, styled); source for re-materializing the stripped templates.
- `STYLE.md` — visual style guide (single source of truth). `TEMPLATES.md` — reference section map + template materialization.


**`validation/`** — `validate_deck.py` (pre-ship lint gate, 0 FAIL to ship), `qa_all.py`
(the full gate: every template + given decks, package integrity, render smoke test, layout
drift), `layout_baseline.json` (the drift fingerprints — `--snapshot` to accept).
**`fonts/`** — Montserrat (headings) and Carlito (Calibri-metric, charts), both bundled and
embedded. `rpe_env.use_font` RAISES rather than let matplotlib substitute a missing face.

`archive/` and `dashboards/` are NOT in this repo — the initial import excluded them. They
live only in Drive. Nothing here references either.
