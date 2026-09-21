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
| CashPlease, CP, small-dollar loans, loans per 1,000 DDAs | CashPlease | `cashplease-deck` |
| ILS analysis review, prep slides, matrix parameters / overrides | ILS prep (not an RPE build) | the `ils-prep-deck` skill |

If a request names a client but not a program, ask which program before building. If it
asks for a combined ARS+ICS+MRPC review, run each subagent in turn and assemble with
`build/assemble_combined.py` (see **Combined decks**) — do not improvise one blended path,
and do not start from an existing combined deck.

## File locations

Paths are resolved from **`RPE_DATA_ROOT`** (`build/rpe_env.py` → `inputs()` / `outputs()`),
set per machine in `.env`. Never hardcode a path in code — if a build's inputs
aren't where `RPE_DATA_ROOT` says, ask Aaron to point at the specific file rather than
guessing, but do not re-ask the whole walk-through each session.

**The pipeline root is `\\PADMIS105\Velocity_company\CSM_Reporting\` on the CSI share,
and it is the ONE copy (Aaron, 2026-09-14)** — one place for every CSM's imports, exports
and project files, now that the pipeline covers all five CSMs' books. Point
`RPE_DATA_ROOT` at it and read and write everything there. It needs the VPN off-site.

```
# Every machine — moved 2026-09-14 from C:\Data Pipelines\RPE Pipeline (a full robocopy,
# a SHA-256 comparison of every file, then a catch-up pass for files written during the
# copy, verified before .env was repointed)
RPE_DATA_ROOT=\\PADMIS105\Velocity_company\CSM_Reporting
```

*History:* `C:\Data Pipelines\RPE Pipeline\` was the local root from 2026-09-09 to
2026-09-14. It was renamed to `C:\Data Pipelines\RPE Pipeline (retired 2026-09-14 - use
CSM_Reporting)\` once the share copy was verified, so nothing can keep reading or writing
it; nothing in it was deleted. Do not point anything back at it.

**There is no second copy, and nothing syncs this tree anywhere. THE ORIGINAL SOURCES
ARE THE BACKUP (Aaron, 2026-09-09).** Every input can be re-fetched from where it came
from: the CSI shares hold the ODD extracts, DCOs, ARS workbooks and MRPCPM analyses, and
the mailbox holds the MRPC / CashPlease reports and the ICS workbooks —
`scripts/watch_sources.py --copy --mail` is how they come back. Outputs are rebuildable
from those inputs by definition, and `Outputs/_Archive/` keeps the newest superseded deck
of each kind per client per period, in a folder per client filed under its CSM
(`_Archive/<CSM>/<id> <client>/`, Aaron 2026-09-14; by CSM 2026-09-15). `promote_month` moves
older decks of the same period and kind to
`_Archive/_older decks - delete after review/<CSM>/<id> <client>/` — never deletes them — and
never moves a hand-made PDF. An existing client folder is reused wherever it sits. The folder
name lives in `rpe_env.ARCHIVE_DIRNAME`; its underscore keeps it above the CSM folders (it was
`Archive/` until 2026-09-15).

Do not introduce a mirror. Two copies of one tree is the two-stores problem that shipped
month-old ICS figures in August: `build/{ics,mrpc}_pipeline/data/` and the VIP store
disagreed, and the deck that read the stale one validated perfectly because it was
internally consistent.

If the root ever moves again the answer is to repoint `RPE_DATA_ROOT` in `.env` — nothing
else. That is the whole reason the path is resolved through `rpe_env` and never written
into code: **do not hardcode a path anywhere,** and do not reintroduce a per-machine
branch in the build code.

**Inputs are sorted into a folder per KIND (Aaron, 2026-09-09).** Everything used to
land in one flat `ARS & MRPC Reports/`. `scripts/watch_sources.py` now files each copy by
kind on arrival. **The folder names live in `rpe_env.INPUT_KIND_DIRS` and nowhere else** —
renaming one is a line there plus a move on disk. Readers glob
`rpe_env.report_dirs()` / `report_files()`, never a literal folder, and that set still
includes the old flat folder, so a file dropped there by hand is still found.

| Input | Folder under `RPE_DATA_ROOT` |
| --- | --- |
| Raw ODDD extracts (zipped, `<id>_ODDD.zip`) | `Inputs/ODDD/` |
| DCOs | `Inputs/DCOs/` |
| ARS workbooks | `Inputs/ARS Workbooks/` |
| MRPCPM analyses | `Inputs/MRPC Analyses/` |
| ICS workbooks | `Inputs/ICS Workbooks/` |
| ICS Charts (mystery shops) | `Inputs/ICS Charts/` |
| MRPCEnrollmentSummary weeklies | `Inputs/Weekly Summaries/` |
| CashPlease data: CashPleaseSummary weeklies and the weekly `ILS-DDA-Count-<YYYY-MM-DD>.txt` (Aaron, 2026-09-16) | `Inputs/CashPlease/` |
| CashPlease production settings (Velocity Product Settings Power BI app, one record per client) | `Inputs/Product Settings/<id>_cp_settings.json` |
| ARS database code tables (product, Reg E, account status codes per client; written by `scripts/ars_code_tables.py` from a database export — the export's settings table holds plaintext FTP credentials and is never copied) | `Inputs/ARS Settings/ars_code_tables.json` |
| Client code sheets (product with its Personal/Business flag, account status, mail flag and Reg E mappings per client; saved by the data team, where a CSM's corrections land) | `Inputs/Code Sheets/` |
| Anything unrecognised (read, never written) | `Inputs/ARS & MRPC Reports/` |
| ICS detailed referral exports (`<id>_ics_detailed referral_v<N>.xls`), for a client with no VIP sheet (hand-landed, member-level, never scanned) | `Inputs/ICS Referrals/` |
| ICS direct-mail new-accounts lists | `Inputs/ICS Direct Mail/` |
| Branch names: `branch_names.csv` (one row per name a source gave a client's branch number, with first/last seen; kept by the morning source check) and `charts_files.csv` (Charts workbooks matched to a client id by hand) | `Inputs/Branch Names/` |
| Client logos (`<clientid>.png`) | `Inputs/Logos/` |
| Monthly debit-card transaction files, one folder per client, **stored zipped**: `<original name>.zip`, one file each (Aaron, 2026-09-17). No deck reads them yet; any reader goes through `rpe_env.txn_files()` / `open_txn()`, which take either form — four files a security agent refuses to let the share hold zipped are still raw, and read the same way. `scripts/zip_txn_files.py` zips new arrivals (safe to re-run) | `Inputs/Txn Files/<id>/` |
| ICS / MRPC client sheets from the VIP dashboards | `Inputs/VIP Data/<PROGRAM>/<id>-<Name>/<id>_<program>.json` |
| Build evidence (figure sidecars) — NOT deliverables | `Build Artifacts/` |
| A launcher build's working files (log, charts, data, result) — its clean deck goes straight to `Outputs/<CSM>/` | `Build Artifacts/launcher/<period>/<id>/` |
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

**Output — ONE destination (Aaron, 2026-07-25), filed by CSM (Aaron, 2026-09-14).** Every
finished deck goes to `Outputs/<CSM>/` — e.g. `Outputs/Aaron Burgard/` — now that the project
covers all five CSMs' books. Program is still distinguished by the filename tag, not by
subfolder. Writers resolve the folder with `rpe_env.client_outputs(id)` (the CSM from
`<RPE_DATA_ROOT>/Client CSM List.csv`, else the CashPlease roster's CSM column, else
`Outputs/_Unassigned/` — never a guessed CSM); readers use `rpe_env.output_decks(pattern)`,
which searches every CSM folder and the flat root but never `_Archive/`. `Outputs/_Archive/`
keeps a folder per client under each CSM. This replaced both the old **Client Presentations** drop and
the per-client `Clients/<Client Name> <clientid>/` copy — do not deliver to client folders.

**`C:\Data Pipelines\` also holds `Renewals Pipeline` — a DIFFERENT project.** It has its
own `Inputs\` and `Outputs\` and is easy to mistake for this one at a glance. RPE is the
sibling folder `RPE Pipeline`, and nothing here ever reads or writes the Renewals tree.

*History, so this does not get "corrected" back:* `C:\Data Pipelines\RPE Pipeline\` was
the CSI/Cowork root after the move off OneDrive (Aaron, 2026-07-17); it was retired to
elsewhere on 2026-08-31, and this file then said "do not point `RPE_DATA_ROOT` anywhere under
`C:\Data Pipelines\`". That guard is spent — the local root is deliberate again as of
2026-09-09. A wrong root still fails loudly rather than quietly, because
`rpe_env.data_root()` raises on a path that is not a directory.

**Write hazard on mounted folders.** Some mounts allow creating and copying files but NOT
deleting — `rm` returns "Operation not permitted". Copy-to-deliver works; if a file must be
replaced or removed, ask Aaron. Confirm the writable target per session.

## Shared conventions (all programs)

**Output — one destination.** Every finished deck is saved to the client's CSM folder in
the pipeline `Outputs\` only — `Outputs\<CSM>\` (see **File locations** above). Program is
distinguished by the filename tag, not by subfolder. No per-client Delivery copies (Aaron,
2026-07-25).

**Decks ship as `.pptx` only — do not generate a PDF** (Aaron, 2026-07-24). PDF is not part
of the pipeline; do not add a LibreOffice/`soffice` conversion step or deliver a `.pdf`
alongside the deck.

**Combined decks — the standard for multi-product clients (Aaron, 2026-08-27).** A client on
more than one program gets ONE combined ARS+ICS+MRPC Executive Review, not three separate
decks. Build each program's deck first (each must pass its own validation gate), then
assemble:

```
python3 build/assemble_combined.py [--ars <ars.pptx>] [--ics <ics.pptx>] [--mrpc <mrpc.pptx>] \
                                   [--cashplease <cp.pptx>] --out <out.pptx>
```

Any two or more programs make a combined deck. **`--ars` is no longer required** (Aaron,
2026-09-01): the first program present in `BASE_PRECEDENCE` (ARS, ICS, CP, MRPC) supplies
the shared shell and Questions/Contact, so 1632 WesBanco and 1734 Altamaha assemble as
**ICS-CP** with no ARS at all. The ARS Appendix stays ARS-only — a deck with no ARS section
has no appendix. `--ics` / `--mrpc` / `--cashplease` are optional, so the same tool builds
a two-program deck:
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
via `rpe_env.report_dirs()` and compares its period to the deck's; on a mismatch the ICS
section falls back to the referrals-only shape — Referrals, Referral Trend, Results by Branch
and the education slides — and the divider drops to "Referrals".

Do not carry an older workbook's figures forward, and do not re-date, align or zero them. An
ICS section that reports an older month than ARS and MRPC is no longer an expected outcome; it
is a defect. The fix is a current workbook, not a carried-forward number.
`assemble_combined.py` prints each section's period so any divergence is visible at build time.

**Contact Us = the managing CSM (Aaron, 2026-09-16).** Every deck's Contact card is the client's CSM
(`Client CSM List.csv`) with that CSM's row in `<RPE_DATA_ROOT>/CSM Contacts.csv`, resolved by
`rpe_env.csm_contact` and drawn or filled through `build/shapes.py`. Never hardcode a person's card; the
template shells' static cards are overwritten at build time. No CSM, or no contacts row, stops the build —
add the row, never fall back to another CSM. Standalone ICS decks add the ICS program contact
(`rpe_env.ICS_PROGRAM_CONTACT`, Cindy Draper) as a second card.

**ICS direct mail.** A sheet's `direct_mail` block (from `Inputs/ICS Direct Mail/`) renders as its own
"Direct Mail New Accounts" slide after Results by Branch; those accounts are never added to referral counts.

**Filename convention:**

```
<clientid>-<yyyy.mm>-<PROGRAM>-<Client Name> <PROGRAM> Results.pptx
```

- `<PROGRAM>` is one of `ARS`, `ICS`, `MRPC`, `CP`, or the included tags joined in
  section order for a combined deck (`ARS-ICS-MRPC`, `ICS-CP`, `ARS-ICS-MRPC-CP`).
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
`month_complete.py` (the ONE definition of a complete month — see **Comparisons use
complete months only**),
`slide_geometry.py` (the per-title geometry contract, promoted out of `ars_pipeline/` so
all three programs can adopt it), plus the post-processors `restyle_fonts.py`,
`summit_slide.py`, `fit_layout.py` (layout-fit + 10pt slide numbers, run by all builders
before save), `strip_dead.py`, `textfit.py`, `branch_names.py` and `assemble_combined.py`.
ARS-specific shared code stays in `build/ars_pipeline/` — `odd_rows.py` (the ODD row
vocabulary: `g`, `fnum`, `swipes`, `spend`, `personal`, `hascard`, `isopen`) and
`before_after.py` (the responder before/after measure) are there because the ODD is an
ARS input. **Both are import-safe on purpose**: `metrics_gen` reads `sys.argv` at module
scope, so importing it RUNS it, and that hazard is why each of these was re-implemented
standalone and then drifted.

The ODD optimizer is `scripts/oddd_optimize.py`; the validator is `validation/validate_deck.py`.
Superseded one-offs, the deprecated pre-`build_ars_gen` ARS recipe (`build_gen`/`build_gen_b`/
`build_swipepct`/`style_tables`/`swap_imgs`), backups (`*_orig`), and the old combined-Marine
helpers were left OUT of this repo (they remain in the pipeline `archive/`) — nothing here
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
python3 validation/qa_all.py --no-tests ...               # skip the unit suite (know why)
```

Run it from the repo `.venv` (`.venv/Scripts/python` on Windows). The Windows Store
`python` has python-pptx but no pytest, and a gate started under it used to skip the whole
unit suite with one quiet line; it now looks for the venv itself and prints a banner when
the suite could not run (2026-09-02).

**Standing rule (Aaron, 2026-08-17): when a defect gets through the gate, add the check
that would have caught it.** Fixing only the instance guarantees the next one ships too.

It runs the full validator on every template (banned words, counts, glyph-aware collisions,
caption overflow, PowerPoint autofit shrink, chart-vs-tile rail) AND compares each slide's
layout fingerprint against `validation/layout_baseline.json` — **DRIFT warnings mean a shared
pass touched slides you didn't intend to change** (the class of regression that otherwise
only a human spots). Review drifts, then `--snapshot` to accept. It also runs an **OOXML
package-integrity check** (`validate_deck.package_findings`): the archive opens and every
member passes its CRC, no part name is written twice, and slide parts are neither duplicated,
dangling nor orphaned.

**There WAS a render smoke test — LibreOffice opened each deck and its PDF page count was
compared to the slide count. It was REMOVED on 2026-09-11 (Aaron): LibreOffice is not going
on the build machine, so the check had never once run there** and every gate closed with a
banner saying so. Do not add it back without the renderer to run it.

**Know what its removal costs.** Nothing in the gate now proves a deck OPENS. The structural
half is recovered by the package check above — including the duplicate-part case, added the
same day after cloning the Summit slide wrote `/ppt/media/image2.png` twice. What is NOT
recovered is everything past "structurally sound": a deck that opens but renders wrong, a
font that does not resolve, an image that will not decode. **Open one deck before a batch
goes to clients.** Three hard-won rules:
1. **Nominal font size is not rendered font size.** `normAutofit` silently shrinks text to
   fit its box, and that scaling is invisible in a render — which is part of why a renderer
   was never the whole answer. The validator FAILs any frame with fontScale <90%; never trust
   nominal font sizes on template-inherited frames.
2. **Box geometry is not glyph geometry.** Text overflows its box silently; the validator
   estimates rendered glyph runs (font-size- and alignment-aware). When adding layout rules,
   fix the BUILDER/geometry contract (slide_geometry.py, fit_layout.py) — never hand-edit
   one deck.
3. **python-pptx is not the file.** Every text/geometry rule reads the deck *through*
   python-pptx, which enumerates a duplicated slide reference as two real slides. All seven
   2026.08 ICS decks passed at 0 FAIL while being unopenable (50 parts, 28 references, six
   parts referenced twice). `package_findings` reads the ZIP directly and is the only thing
   in the gate that can see that class of defect — added 2026-08-17 after it shipped, and
   the last line of defence since the render test was removed.

**Swap gate — a text swap that matches nothing FAILS the build (2026-07-25).** The ARS
builder records every find-string that matched no shape and exits non-zero listing them. This
exists because a silent no-op is the worst failure mode in this pipeline: the slide keeps the
TEMPLATE's numbers and ships looking perfectly plausible. It is how the entire Appendix and the
"Profit This Month" tile carried the reference client's figures into every deck until
2026-07-25. Related rule: **resolve slides by TITLE, never by index** — `build_ars_gen.SB(title)`
raises if the title is absent, whereas `S[n]` silently points at the wrong slide the moment the
template gains or loses one.

**The closing slide carries the cover's month (2026-09-17).** Questions & Discussion reads
"<client>  •  <reporting month>", the same client and month as the cover. Every 2026.09 ARS deck
(33, combined decks included) shipped "<Client>  •  July 2026" there under a September cover,
because `build_ars_gen` swapped only the client name on that slide. `validate_deck.closing_month_findings`
FAILs any deck whose closing line names a different month or client than the cover.

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

**Visual style guide.** Every client-facing deck — the ARS / ICS / MRPC / CashPlease
Executive Reviews, the standalone CashPlease module and the ILS review prep slides — follows
`templates/STYLE.md`: the palette and type roles (`build/brand.py`), the slide anatomy
(numbers, logos, pills), the shell (title lists only the included products; reporting month
= generation month), callouts with the one drop shadow (pies and donuts flat), tables, chart
standards (`MMM'YY` axes, `TEAL` lines over navy, no mark in the canvas color), selection on
the slide / source in the notes, and where each rule is enforced. **Read it before building
any deck, and keep it as the single source of truth for visual style.** `tests/test_style_doc.py`
fails if it cites a file that no longer exists.

**Writing style.** All client-facing text follows Aaron's rules (Obsidian
`Claude/Operating Instructions.md`). Banned words include: robust, comprehensive,
leverage, seamless, delve, and the banker-deck list — engine, lever, lift (as prose;
"ARS Lift Matrix" as a proper slide name is fine), ramping, healthy, predominantly,
companion, seasoned book, annuity. No superlatives or unsupported higher/lower claims.

**Comparisons use complete months only (Aaron, 2026-09-17).** "Don't calculate YoY or
comparisons on partial months, only use complete months." Marine FCU 1539's 2026.09 NSF/OD
slide said "-98% Items YoY (Aug 25 → Aug 26)": the extract was pulled 09/04/26 with whole
August swipes and spend, but only 390 NSF/OD items for August against 19,451 in July.

`build/month_complete.py` is the one definition, shared by every program. A month is
incomplete for a MEASURE when the data was pulled before it ended (the ODD member's
`(MMDDYY_HHMMSS)` stamp, a weekly's "Report Generated" date, a VIP sheet's `data_pull`), or
when its total is below half the median of the six months before it (trailing months only,
at most two, baseline median 50 or more). Completeness is per measure: Marine's August is
complete for swipes and spend and incomplete for NSF/OD.

- Every YoY, month-over-month, latest-month tile, trend endpoint and trailing window uses the
  last complete month of the measures it reads. A computation that reads several measures
  (the swipe-tier window, before/after) uses months complete in all of them.
- A left-out month is STATED — on the slide ("Aug 2026 left out: incomplete in this
  extract.") and with its figures in the notes — never zeroed, never charted as a collapse,
  and its slide is never dropped. Status snapshots (Elig, Reg E, account status) are not
  activity and still read the snapshot month.
- ARS: `metrics_gen` and `ticket_calc` call `month_complete.odd_completeness`; the workbook's
  Key Trends spend goes through `complete_rows` (in `build_ars_gen`, `charts_gen`, the
  one-pager and the performance dashboard). CashPlease: `cp_extract` holds a `*` roll-up for a
  month not yet ended out of `monthly`. MRPC: `build_mrpc_gen.complete_series` trims
  `performance_vs_goal` and `revenue.by_month`. ICS branch YTD referrals cannot be split by
  month, so the notes say they include the month to date.
- Do not write a new "latest month" read of an activity series without going through it.

**Describing movement — the +/-2% band (Aaron, 2026-08-31).** A sentence that says a
measure moved must agree with the figures beside it:

| Change | Say |
| --- | --- |
| within **+/-2%** | "almost flat" |
| **positive** | state the increase — the figures and the % |
| **negative** | say it did not have an impact on that measure |

The verb is DERIVED, never written as a constant. The Average Ticket caption hardcoded
"ticket holds through response" and shipped that over declines of 5.2% to 8.6% on six
2026.08 decks (1509, 1537, 1539, 1549, 1676, 1705); the same sentence hardcoded "monthly
swipes rise", which real clients happen to do, so it went unseen until the golden deck's
synthetic ODD fell 3.0% and still said "rise". Both now follow the data
(`build_ars_gen.py` slide 11, `ticket_chart.py`), as does the chart title above the bars.

**A claim with no figure behind it is not checkable.** "NSF/OD activity stayed roughly
flat" shipped in Marine FCU commentary while NSF/OD had risen 27% (0.40 -> 0.50 per
responder per month) in the extract that slide was built from. Nothing contradicted it
because nothing had to: the clause carried no number. State the figures, or do not make
the claim.

**`validate_deck.claim_consistency_findings` FAILs a mismatch.** It reads one sentence at
a time and matches each claim to its NEAREST figure pair. It distinguishes a COMPARISON
("responders carry lower balances than non-responders, $924 vs $2,477" — two groups, one
moment) from a MOVEMENT ("spend rose from $556 to $1,077" — one measure, two times);
reading the first as the second failed six correct slides. It also honours negation, so
"did not increase" is not read as an increase. See `tests/test_claim_consistency.py`,
where half the cases are the false positives that had to be designed out.

## Cadence

ARS, ICS and MRPC deliver **monthly** — one deck per client per month, per the table
below. **CashPlease is weekly**, and is the exception to everything in this paragraph. Nothing in this table is quarterly: where a quarterly input exists (the ICS
workbook) it gates which SECTIONS carry current figures, never whether the deck ships.
The Executive Summit one-pagers are a separate, non-monthly delivery — see
**Executive Summit one-pagers** below.

| Program | When | Scope |
| --- | --- | --- |
| ARS | Monthly | Every ARS client, each month — MM or SM path per client |
| MRPC | Monthly | Every MRPC client, each month |
| CashPlease | **Weekly** | The one program that is not monthly. Bradford Sanders' "CashPlease Summary" workbook arrives weekly and the build **always uses the most recent one** (Aaron, 2026-09-01) — not the one nearest a deck's period. So a CashPlease section inside a monthly Executive Review can report a LATER date than the ARS/ICS/MRPC sections beside it, and that is intended: the CP pill keeps its own `PTD · <date>` and is never re-dated to match its neighbours. `assemble_combined.py` prints each section's period so the divergence is visible at build time. Scope is the `### CashPlease roster` table in `clients.md` — never the workbook, which carries every Velocity CashPlease client across all CSMs. |
| ICS | Monthly | **The ICS deck ships monthly like the other two (Aaron, 2026-08-31)** — what is quarterly is the WORKBOOK, not the delivery. Referrals come from VIP monthly. **Financial detail ships ONLY when the ICS workbook is for the deck's own period (Aaron, 2026-08-28).** This REPLACES the previous carry-forward rule: a monthly build used to carry the last workbook's financial sections forward, which kept them auditable in the source notes but dated them as current on the slide face — 1537 and 1676 both stamped "PTD · August 2026" on figures from 2026.06 and 2026.07 workbooks. The builder now resolves the newest ICS workbook for the client from `Inputs/ARS & MRPC Reports/` and, if its period differs from the deck's, omits the workbook-driven sections entirely. Referrals, Referral Trend, Results by Branch and the education slides are unaffected. Missing-section guard still stops a build whose data sheet was never populated. |

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

### Executive Summit one-pagers — NOT a canned deliverable

**The Summit one-pagers are hand-built, per attendee, and are never generated on a schedule
(Aaron, 2026-08-31).** Summits run a couple of times a year and the one-pager goes only to
clients who are ATTENDING. It is a selective document: the point is to show that attendee
their strongest metrics, which is a judgement call about that client, at that Summit, for
that audience. That judgement is Aaron's — it is not a template fill and there is no
"correct" set of figures to automate toward.

So:

- **Do not add the one-pager to the monthly run.** `scripts/build_month.py` builds the
  monthly ARS/ICS/MRPC reviews and must not learn to emit one-pagers. It does not today —
  keep it that way.
- **Do not build one for a client who is not attending**, and do not build the full roster
  "so they are ready". Ask Aaron which attendees need one.
- **Do not pick the metrics.** `build/ars_pipeline/build_ars_onepager.py` renders a
  one-pager from figures it is given; which story it tells is Aaron's call. Ask rather
  than choosing what looks best.
- The monthly reviews are the opposite in every respect — every client, every month, same
  slides, no curation. Conflating the two has caused real errors: a monthly deck's
  reporting month was once derived from the twice-yearly Summit date, which is wrong ten
  months out of twelve (fixed 2026-08-29, commit `02def05`).

The Summit slide that every monthly deck carries is a different thing again: a standing
title/branding slide inserted by `build/summit_slide.py`, unrelated to who attends. No
builder depends on the date printed on it.

## Delivery dashboard

```
python3 scripts/dashboard.py [--period 2026.09] [--port 8787] [--no-source]
```

Serves `http://127.0.0.1:8787/` — data readiness, what is built, and what still
needs sending, per client for one period. Loopback only: it exposes a write
endpoint and the delivery log is not public. `scripts/deck_status.py <period>
--json out.json` produces the same document without a browser.

**Where each fact comes from.** The dashboard invents nothing; it displays
`deck_status.collect()`.

| Fact | Source |
| --- | --- |
| Who gets a deck | `clients.md`, via `build_month.read_roster` — the same parser the builder uses |
| Has the data team landed it | every CSM's ODD folder (`deck_status.SRC_ODDD` — all five, each with its own month-folder naming; see **Daily source watch**) and `\\PADMIS105\Velocity_clientreports\<YYYY.MM>\<Account Manager>\` |
| Can the build run | `Inputs/` — the copy the builders actually read |
| Built | `Outputs/<CSM>/<id>-<period>-*.pptx` (via `rpe_env.output_decks`) |
| Sent | `Build Artifacts/deliveries.json` |

Override the share paths with `RPE_SRC_ODDD` / `RPE_SRC_REPORTS`; they are never
hardcoded, for the same reason `RPE_DATA_ROOT` is not.

**The CSI shares need the VPN (Aaron, 2026-08-31).** Off VPN they are not empty,
they are *unknown*, and the dashboard says so rather than reporting a full cycle
of phantom gaps. The input columns stay accurate either way.

**Sent is recorded, never inferred.** A deck in `Outputs/` proves it was BUILT.
Nothing on disk knows whether it reached the client, so sent-state is written to
`Build Artifacts/deliveries.json` by the dashboard's Mark sent button (Aaron,
2026-08-31) — bookkeeping, so it stays out of `Outputs/`. A damaged log raises
rather than reading as "nothing sent", which would invite sending twice.

**An ODD extract in `Inputs/` is only current if the SOURCE says so.** `Inputs/ODDD/`
holds `<id>_ODDD.zip` with no period in the name, overwritten in place each
month — so last month's extract sits at the same path under the same name and
"a file is there" does NOT mean this period's data is there. The dashboard
reports that as **stale**, and stale blocks exactly as hard as missing: a build
on the previous month's ODD completes, validates, and reports the wrong month.
Off VPN the period cannot be confirmed and is reported as unknown, not current.

**ICS workbooks arrive by email, not on the share (Aaron, 2026-08-31).** They
have no source-side signal, so their source column is `n/a` and a missing one
does not block — without a workbook for the period the ICS section builds
referrals-only, which is a valid deck.

### Daily source watch

```
python scripts/watch_sources.py [--notify] [--dry-run] [--period 2026.09 ...]
powershell -ExecutionPolicy Bypass -File scripts\register_watch_task.ps1 [-Time 08:00] [-Unregister]
```

`deck_status.py` answers "is it there now"; `watch_sources.py` answers "what
landed since I last looked" (Aaron, 2026-09-08). It scans this month's and last
month's folders on the CSI shares — ODD extracts in all five CSMs' folders on
`Velocity_company` (see the 2026-09-14 paragraph below), DCOs / ARS workbooks / MRPCPM
analyses on `Velocity_clientreports` — diffs the
inventory against the one it saved last run, and reports files that are new,
re-landed (same name, new bytes) or gone, roster clients first, each with whether
the copy the builders read is already current. Nothing is copied
automatically. It reuses `deck_status`'s share roots (and their `RPE_SRC_*`
overrides) and the `clients.md` roster.

State is bookkeeping, so it lives in `Build Artifacts/`:
`source_watch.json` (the last inventory), `source_watch.log` (appended per run),
`source_watch_latest.md` (the latest report). The first run is a baseline and
reports counts, not news. **Off VPN it exits 2 and leaves the saved inventory
alone** — saving an empty one would make every file "new" the next morning.

`register_watch_task.ps1` schedules it as the Windows task **"RPE Source Watch"**,
daily at 08:00 as the logged-on user (the share needs those credentials and the
toast needs a desktop), catching up a missed run when the laptop wakes.
Registered on this machine 2026-09-08. `--notify` raises a Windows toast only when
there is news or the shares were unreachable; a quiet day is silent.

**The daily run also reads the MAILBOX (Aaron, 2026-09-09).** Two kinds of input never
land on a share: **MRPC and CashPlease reports from Bradford Sanders**, and **ICS workbooks
from Matt Milliman**. `--mail`, which the scheduled task passes, takes them from Outlook
via `scripts/mail_sources.py` and files them by kind alongside everything else.

- **Outlook COM, not Graph** — the task already runs as the logged-on user, so the desktop
  profile is signed in and there is no app registration, secret or consent to own. An
  unreachable mailbox is REPORTED and skipped, never fatal — the share check runs every day
  regardless.
- **The mail step cannot hang the run (2026-09-10).** A COM call into an Outlook that is
  still starting up, syncing, or showing a dialog blocks with no timeout and no way to
  interrupt it from a thread: the 08:00 runs of 2026-09-09 and 2026-09-10 sat in it for the
  full 30 minutes, the scheduler killed them, and the share check — finished in under a
  minute — died unwritten with them. So: the share results (log, report, inventory) are
  written BEFORE the mail step; the mail step runs as its own process
  (`watch_sources.mail_step`, `MAIL_TIMEOUT` = 10 min) and a timeout is reported as
  "TIMED OUT", not fatal; and `mail_sources._outlook()` attaches to the running Outlook
  with `GetActiveObject` first — which fails at once while Outlook is starting, instead of
  blocking — and only launches a windowless instance with `Dispatch` when none is running
  (it exits with the process). Outlook does NOT have to be open for the task; it merely
  goes faster when it is.
- **Read-only.** Nothing is marked read, moved, deleted or replied to.
- **Senders are matched on the resolved SMTP address**, never the display name, and each
  sender may only supply their own kinds — an ICS workbook from the MRPC sender is reported
  and skipped. An Exchange sender's `SenderEmailAddress` is an X500 path, so the address is
  resolved through the Exchange user first.
- **Inbox AND Archive**, plus subfolders. A rule files both senders straight into Archive:
  an Inbox-only scan read 35 messages and 123 attachments and found neither of them.
- **Only the newest of each thing**, the same rule the share copier uses. A mailbox holds
  every weekly ever sent — a 120-day scan turned up twenty, of which the pipeline reads one
  — and it holds ICS workbooks four months older than the ones already in `Inputs/`.
- An attachment whose filename does not match `<id>-<period>-<kind>` is **parked in the
  legacy folder and reported**, never guessed at.

**The daily run also keeps the ICS referrals query current (Aaron, 2026-09-17).** With
`--ics-referrals`, which the scheduled task passes, `scripts/ics_referrals_pull.py` merges any
result of the all-clients ICS referrals query saved in `Inputs/ICS Referrals/` into
`ics_referrals.csv` and rewrites the query there to pull only referrals issued since the newest
one merged. The start is that referral's DAY, so the window overlaps the last pull on purpose;
the merge replaces a referral's rows (client + account + issue date) with the newer pull's, so
nothing counts twice. A morning nobody ran the query leaves the start where it was — a skipped
day widens the next window, never leaves a gap. Older referrals keep the account, spend and
balance columns of the pull that brought them in; a full pull (`@since = null`) refreshes them.
With `--branch-names` (also in the task) it then adds any new branch name from the Charts
workbooks and that pull to `Inputs/Branch Names/branch_names.csv`; a Charts file whose name does
not identify one client is listed in the report for a row in `charts_files.csv`.

**The daily run also copies (Aaron, 2026-09-08).** With `--copy`, which the scheduled
task passes, every file on the shares for **every client except a stopped one** (see the
2026-09-14 paragraph below) that `Inputs/`
lacks, or holds a different landing of, is copied into `Inputs/` — DCOs, ARS
workbooks, MRPCPM analyses and ICS workbooks each to their own folder, the ODD extract
to `ODDD/<id>_ODDD.zip`.

**ODD extracts come from ALL FIVE CSMs' folders (Aaron, 2026-09-14).** The data team
lands each CSM's extracts in that CSM's own folder, so `deck_status.SRC_ODDD` lists all
five as `CSM=path` entries (override with `RPE_SRC_ODDD`, same format; a bare path still
works): Aaron `Velocity_company\Aburgard\ODDD`, Daniel Wood `Dan Wood\OD Data Dumps`,
Gregg Miller `GMiller\OD Data Dumps`, James Gilmore `JamesG\OD Data Dumps`, Jordan
Berkowitz `JBerkowitz\OD Data Dumps`. **Each CSM names month folders differently** —
`2026.09 Sep` (Aaron), `2026.09` (James), `September, 2026` (Jordan, Gregg), `090126`
(Dan, the first of the month) — and `deck_status.odd_folder_period` is the one place
that reads them; a folder it cannot read (`Archive`, `2025`) is not a month and is
skipped. **Every client's files are copied — ODD extracts, DCOs and workbooks alike, for
all five CSMs' books, not only roster clients** — except the clients `clients.md` marks
as stopped (`read_roster`'s skipped rows: 1437 Canandaigua, 1174 PointBank, 1658
Truliant), whose files the data team keeps landing. `clients.md` still decides what gets
BUILT; the copy only decides what is on hand. If `clients.md` cannot be read the copy
falls back to roster clients only, which copies nothing rather than everything. If two
CSM folders hold the same client and month (a handover), the more recent write is
taken. **One unreachable CSM folder counts as off VPN**: the run exits 2 and saves
nothing, because otherwise every extract in that folder would read as gone. Copy-only: nothing in `Inputs/` is ever deleted by a copy (some mounts
refuse deletes anyway); a `.part` file is written and renamed over the target so a
copy that dies half way never leaves a truncated extract under the real name, and the
size is verified after. **The ODD extract is only ever copied from the newest month on
the share for that client.** The watch scans two months and the local copy carries no
period in its name, so once this month's extract is in `Inputs/` last month's at source
"differs" from it forever — copying it back would be the stale-ODD failure in its
purest form. `copy_plan` is where that rule lives, and `tests/test_watch_sources.py`
pins it. A client `clients.md` marks as stopped (1437 Canandaigua, ended) gets nothing
copied at all — no extract, DCO or workbook — even though the data team keeps landing its
files.

**A "differs" file is overwritten only when the SOURCE is the newer write.** A local
copy modified after the landing is a deliberate change, not a re-landing — a workbook
opened and saved in Excel so its formulas carry values, which is what the extractors
read. The first copy run clobbered 1539's recalculated 2026.08 workbook with the
share's never-evaluated original and every ARS figure for Marine FCU read 0
(2026-09-08; recovered by recalculating in Excel). **A landed workbook can arrive with
its formulas unevaluated**: openpyxl then reads the template defaults (1 month, 0
mailings, $0). `build/ars_pipeline/base_guard.py` is the one definition of that
check: both ARS extractors and the ARS builder exit with `UNEVALUATED WORKBOOK: ...`
on such a base, and the dashboard refresh reports the row as "carries no calculated
values" rather than rendering zeros. The fix is to open the workbook in Excel, save,
and rebuild. `tests/test_base_guard.py` pins that every ARS entry point uses it.

Because the copy happens before the 08:30 dashboard refresh, a new month's
workbooks reaching `Inputs/` roll the performance artifact forward the same morning.

**...and prunes what a newer version supersedes (Aaron, 2026-09-08).** With
`--prune`, also passed by the task, a workbook-ish file in `Inputs/` is deleted
when a NEWER version of the same thing is there: same client id and kind (DCO, ARS
workbook, MRPCPM analysis, ICS workbook) with a later period, or the same weekly family
(MRPCEnrollmentSummary, CashPleaseSummary) with a later stamp. The newest of each group
is always kept; a file that is the only one of its kind for a client is never touched
however old (1174's lone 2026.07 DCO, 1537's 2026.06 ICS workbook); two files with the
same version key (a weekly and its "- Copy") are ambiguous and both stay; the ICS Charts
workbooks, the ODD extracts and anything unpatterned have no "newer version" this code
can identify and are left alone. The newer file must exist and be non-empty at the
moment of deletion. `prune_plan` holds the rule; the tests pin it. Consequence: the
delivery dashboard's input columns for a PAST period read "not copied" once that
period's inputs are pruned — the deck is built and that is the column that matters.

**The watchdog — the unattended 08:00 fire has to be watched from OUTSIDE (Aaron,
2026-09-11).** Three mornings running (2026-09-09, -10, -11) the daily task fired at
08:00 and produced nothing: no log entry, no report, killed by Task Scheduler at its
30-minute limit. The process was not hung in our code — it was created SUSPENDED and
never executed a single instruction (0 handles, 0 CPU, one thread parked in
Wait/Suspended; a real block in SMB or Outlook COM has loaded modules and live CPU).
Every run started by hand, on an awake machine, finished normally in 1-3 minutes,
including immediately after diagnosing this — so a code-level timeout cannot be the
fix: the process never gets far enough into our code to run one. The one plausible
culprit (never positively confirmed) is Symantec Endpoint Protection, installed on
this machine, intercepting process creation and relaunching under its own supervision
— a manual retry showed every python launch in this pipeline appearing twice in the
process list, the second a direct child of the first with an identical command line
and creation timestamp, consistent with exactly that kind of hook.

```
powershell -ExecutionPolicy Bypass -File scripts\register_watchdog_task.ps1 [-Time 08:15] [-Unregister]
```

`scripts/watch_task_watchdog.ps1` runs as its own scheduled task, **"RPE Source Watch
Watchdog"**, a fixed offset after the main task (default 08:15, 15 minutes after the
main task's 08:00). Not a background thread of the main task — if whatever suspends
the main process can suspend it, a thread living inside that same process is exactly
as stuck; a second, independently-triggered task is the only vantage point actually
outside the failure. Each firing: if `source_watch_latest.md` is already fresh
(within 3 hours), it exits silently — the common case, every healthy morning. Otherwise
it looks for a `watch_sources.py` process matching the suspended signature (near-zero
CPU, near-zero handles, old enough — 4+ minutes — that a healthy run would have
finished), kills the whole process tree, and retries the main task; up to two
kill-and-retry cycles before giving up and logging for a human. Every attempt is
appended to `Build Artifacts/source_watch_watchdog.log`. Registered on this machine
2026-09-11, verified end-to-end via `Start-ScheduledTask`. The kill-and-retry path
is code-reviewed, not fire-tested against a genuinely OS-suspended process — this
environment's sandboxing refused the `CREATE_SUSPENDED` P/Invoke needed to manufacture
one (`ERROR_INVALID_NAME` even on a trivial `notepad.exe` control case), so treat that
one path with a little more scrutiny before trusting it blind.

`register_watch_task.ps1` had drifted from the live task it describes — the
registered task already carried `--mail` (added when the mailbox step landed,
2026-09-09) but the checked-in script's `Argument` string did not, so re-running it
would have silently dropped mail reading. Fixed 2026-09-11; both now agree.

### The performance dashboard artifact — refreshed after each source check

```
python scripts/refresh_performance_dashboard.py [--period 2026.08] [--force]
python scripts/refresh_performance_dashboard.py --mark-published
```

The "RPE Client Performance" artifact
(`https://claude.ai/code/artifact/71e542f6-cb48-4386-ae73-708e513c854b`) is the
cross-client, cross-product page Aaron asked for on 2026-09-08: one section per
program (ARS, ICS, MRPC, CashPlease) with a ranked bar, a metrics table and trend
sparklines, and a deck roster. It is a static page with its dataset embedded.
`refresh_performance_dashboard.py` rebuilds that dataset from the same inputs the
deck builders read (ARS workbooks + DCOs through the ARS extractors, mailing response
from the shipped deck's figure sidecar, the VIP ICS / MRPC sheets, the newest
MRPCEnrollmentSummary and CashPleaseSummary weeklies — the last through the
in-repo `build/cashplease_pipeline/cp_extract.py`, so the page and the CashPlease
decks are computed once), injects it into `scripts/perf_dashboard_template.html`, and writes the
page and its bookkeeping to `Build Artifacts/perf_dashboard/`. **The period is the
newest ARS workbook in `Inputs/`**, so the page rolls forward when a month's workbooks are
copied, not before. **Within that cycle every client shows its own newest figures**
(Aaron, 2026-09-08): the newest ARS workbook, shipped-deck sidecar and built deck at or
before the cycle period, with the row tagged when that is older than the cycle. A
cycle-only page went blank for three ARS clients and every deck the first morning of a
month. It ends with `STATUS: changed|unchanged`, comparing a content hash (generation
date excluded) to the hash last published.

Publishing needs the Artifact tool, so the script never publishes. The Claude
scheduled task **`rpe-dashboard-refresh`** (daily 08:30, after the 08:00 source
watch; stored under `~/.claude/scheduled-tasks/`) runs the script, republishes to the
URL above only on `changed`, then runs `--mark-published`. It runs while the Claude
desktop app is open and catches up on next launch. **Do not create a new artifact
for this page** — republish to the URL, or the link people hold goes stale.

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
- `CHANGELOG.md` — **the record of corrections and changes** (Aaron, 2026-09-01): a
  moved number or source, a changed claim, AND a change to what a slide renders.
  Post to it whenever you change pipeline behavior. This used to say "changes that
  move a client-facing number or its source", and that reading kept the MRPC
  invisible-retention-line fix out of the file entirely.
- `requirements.txt`, `.env.example` — runtime deps; `RPE_DATA_ROOT` and friends.
- `docs/` — the PRDs: `PRD-2026-08-26-repo-portability-and-response-rates.md`,
  `PRD-2026-09-11-rpe-client-performance-artifact.md` (the cross-client performance page:
  what it is for, where each figure comes from, and why the script never publishes).

**`scripts/`**
- `oddd_optimize.py` — raw ODD → data pack (`oddd_pack.md` + `oddd_metrics.json`); Reg E / account-status classifiers, funnel, mix.
- `build_month.py` — builds the monthly ARS/ICS/MRPC reviews for one period from the `clients.md` roster. Never emits Summit one-pagers.
- `deck_status.py` — the status engine behind the dashboard: for one period, what data has landed, what has been built, and what has been sent. Reuses `build_month.read_roster` so there is one answer to who gets a deck.
- `dashboard.py` — the local delivery dashboard (see **Delivery dashboard**).
- `watch_sources.py` — the daily CSI-share check: what ODDD / DCO / workbook files landed since the last run, with local-copy state (see **Daily source watch**).
- `ics_referrals_pull.py` — the `--ics-referrals` step: merges each ICS referrals query result saved as `Inputs/ICS Referrals/ics_referrals <date>.csv` into one `ics_referrals.csv` (a referral = client, account, issue date; a newer pull replaces an older pull's rows for the same referral) and rewrites `ICS Referrals - new since last pull.sql` beside it with `@since` = the day of the newest referral merged. The query itself (`sql/ics_referrals_all_clients.sql`) is run by a person; Claude cannot reach that database.
- `ils_dda_count_mail.py` — saves the newest "ILS Management Server DDA Count" email body (Charles Baker's weekly forward) word for word from Outlook as `Inputs/CashPlease/ILS-DDA-Count-<sent date>.txt`, the CashPlease loans-per-DDA denominator. Run by the CSI Email Monitor task (`C:\Data Pipelines\Email Pipeline\run-monitor.ps1`) before its Claude step (Aaron, 2026-09-17); never overwrites a saved week whose table differs.
- `mail_sources.py` — the `--mail` step: reads Bradford's and Matt's attachments out of Outlook via COM, files them by kind, newest-only (see **Daily source watch**).
- `register_watch_task.ps1` — registers / removes the Windows scheduled task "RPE Source Watch" that runs it daily.
- `watch_task_watchdog.ps1` — detects a "RPE Source Watch" run Windows created suspended and never executed, kills it, and retries (see **The watchdog**).
- `register_watchdog_task.ps1` — registers / removes the Windows scheduled task "RPE Source Watch Watchdog" that runs it.
- `refresh_performance_dashboard.py` — rebuilds the "RPE Client Performance" artifact's dataset and page into `Build Artifacts/perf_dashboard/`, with change detection against the last published hash (see **The performance dashboard artifact**).
- `perf_dashboard_template.html` — that artifact's page, with a `__DATA__` slot the refresh script fills. Edit here, never in the published copy.
- `ars_launcher.py` — builds one client's ARS deck, or with `--combined` one deck with ARS plus every other clients.md program whose data is on hand (`program_availability`: ICS from VIP or the local ICS files, MRPC from VIP), into Outputs without Claude (`status | build <id> [--combined]`): checks the product list, `clients.md`, the combined-deck rule, sent state and input currency first, works in `Build Artifacts/launcher/<period>/<id>/`, and puts a 0-FAIL deck straight into `Outputs/<CSM>/`, archiving what it supersedes. No staging step: each CSM reviews, PDFs and emails the deck from Outputs (Aaron, 2026-09-15).
- `ars_launcher_web.py` — CSM Sheila, the Smart Helper for Executive Insights, Layouts & Analytics (was ARS Deck Builder until 2026-09-16, then briefly WILL), the browser front end for `ars_launcher.py`: a 127.0.0.1-only server whose page lists the `clients.md` ARS clients, shows the launcher's checks and runs `ars_launcher.py build` as a child process, streaming its steps. Builds run one at a time; one asked for while another runs waits in a first-in, first-out queue, the client page offers "Build ARS only" and, when another program has data, "Build combined (ARS + …)" (Aaron's multi-program clients get only the combined one), and the list shows Building / Queued #N, or a red Error <period> pill when the client's last build was not put in Outputs (its button then reads Retry build). Every API call needs the token baked into the page and a localhost Host header; "Show in File Explorer" opens only a file under Outputs. The header shows the five newest CHANGELOG.md entries and links the full log (`/changelog`). **It serves from memory and refreshes behind the page (2026-09-17):** the client list is rebuilt in the background when it is older than `CLIENTS_TTL` (60 s), on "Refresh", or when a build finishes, and the page shows its age ("List as of …") and the last list it had (sessionStorage) while loading; builds this server ran (Building, Queued, Error, the deck put in Outputs) and Lift Matrix tags are laid over the stored list on every request. A client's status older than `STATUS_TTL` (600 s) is shown at once, marked "checking again", with its Build buttons held until the fresh check arrives; "Check again" is always a fresh read, and a client whose list row changes (deck, sent, last build) has its status dropped. Repeated share questions (reachability, report folders, VIP manifest, cycle period, the CSM list row) are kept for `SHARE_TTL` (60 s) by `install_share_caches()`, which only `main()` installs: `ars_launcher.py build` runs as its own process and its pre-build checks never see these caches. It decides nothing itself.
- `launchers/` — `Build ARS Deck.bat`, `ARS Deck Builder GUI.bat` (starts `ars_launcher_web.py`), `ARS Deck User Guide.html` (released to the CSM_Reporting root) and `runtime.cmd`, which unpacks the released Python to `%LOCALAPPDATA%\RPE` on first use.
- `release_launcher.ps1` — copies the code to `<root>\Tools\RPE` and the .bat files to the root; `-Runtime` also ships the zipped Python. **The launcher runs the released copy: re-run after any change, `clients.md` included.**
- `issue_pages/` — the two team issue pages, **ODD and Workbook Issues** and **CSM Data Gaps** (published as Claude artifacts, copied to `Notes/`). `build_issue_pages.py [--no-scan] [--no-notes]` runs the chain after `refresh_performance_dashboard.py`: `gaps_matrix.py` (per-client gaps -> gaps.json), `noprog_odd_dates.py`, `missing_wb_history.py` (every month on the reports share for the Missing Workbook clients), `business_flags.py` / `mail_flags.py` (full ODD scans; `--no-scan` reuses them), `odd_wb_by_csm.py` (the ODD page, with the Lift Matrix date check), `gaps_inject.py` + `gaps_template.html` (the Data Gaps page). `clients_products.py <export.csv>` loads a new Velocity client/product export. Paths come from `common.py` via rpe_env; working data and pages live in `Build Artifacts/issue_pages/` because they carry client names and products. Publishing the artifacts needs Claude.
- `perf_workflow.html` — the page's linked "How the decks are made" page (inputs, outputs, folder map), published beside it as `workflow.html`.
- `perf_clients.py` — which clients the page lists: every current client on the reports share, with programs inferred for clients `clients.md` does not cover.
- `perf_overview.py` — the page's Client overview figures, and the per-client code counts, from each ODD extract (cached per extract).
- `perf_actions.py` — the page's CSM action items: Lift Matrix flags in workbook filenames, and ODD codes the client's ARS code tables do not list. Never maps a code; the CSM corrects the client's code sheet.
- `zip_txn_files.py` — zips each file in `Inputs/Txn Files/` to `<name>.zip` beside it, checks the zip's size and CRC against the original, then deletes the original (a refused delete is reported). Re-run it after landing new transaction files.
- `ars_code_tables.py` — extracts ONLY the product, Reg E and status code tables from an ARS database export into `Inputs/ARS Settings/`; the settings table (plaintext credentials) is never parsed past its header.

**`build/ars_pipeline/` — the ARS pipeline (client-agnostic)**
- `build_ars_gen.py` — the ARS deck assembler: populates the `ars_template.pptx` shell, inserts Product Mix and Excluded Accounts, writes source notes, adds the Contact slide, moves the Appendix after Contact, restyles fonts, runs the logo/slide-number branding pass.
- `metrics_gen.py` — ~105 chart metrics from the ODD (streams the `.zip`).
- `charts_gen.py` — renders the 28 chart PNGs; `DIM` = each chart's pixel size (must match its slide box aspect).
- `chart_lib.py` — shared take-rate-by-branch renderer (personal orange / business navy; identical size).
- `base_tab_extract.py` — SM financials from the workbook (+ DCO).
- `base_guard.py` — refuses a workbook whose formulas were never evaluated (extracts as 1 month, 0 mailings, $0); called by both extractors, the builder and the dashboard refresh.
- `extract_base_gen.py` / `extract_lift.py` — MM financials / Lift Matrix rows.
- `lift_window.py` — the ONE reading of the Lift Matrix MM window (Start/End Date, the data month, `in_window` / `data_past_end`), import-safe. `extract_lift` puts it in lift.json; `ars_launcher.lift_checks` stops an MM client's build when the data month is past the End Date or the workbook filename carries the data team's Lift Matrix flag.
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
- `before_after.py` — the responder before/after measure (cohort, windows, winsorizing,
  pooling), imported by BOTH `metrics_gen` (the monthly deck) and `responder_activity`
  (the Summit one-pager). **The Summit and the monthly decks use the same logic**
  (Aaron, 2026-09-08): the two used to compute it four different ways and the one-pager
  reported True Sky at +118% while the client's own deck said +103%.
- `slide_geometry.py` — the builder/geometry contract layout rules are fixed in (CLAUDE.md rule 2).
- `combined_insights.py`, `insight_charts.py`, `combined_insight_slides.py` — six views from James
  Gilmore's deck (revenue by mailing, responders vs mailed non-responders, card account health,
  take rate and Reg E by branch, Branch Scorecard with number and name, ARS scorecard), merged from
  `test/james-aaron-combined` 2026-09-17 and still OPT-IN: `build_ars_gen` adds them only when
  `RPE_JAMES_SLIDES=1`.

*Standalone ARS tools — run by hand, not part of the deck chain:*
- `build_ars_onepager.py` — the 8.5x11 print one-pager. Deliberately skips
  restyle_fonts / fit_layout / validate_deck, which enforce the 13.33x7.5 deck contract.
- `responder_activity.py` — reads the raw ODD for the one-pager: eligible count, reach,
  depth, transactions over the ask. The before/after figures come from the shared
  `before_after.compute`, not from this file.
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
- `branch_names.py` — branch id → name lookup shared by the ARS chart renderers (since 2026-09-17 `metrics_gen` puts the names on every branch chart, table and caption when most of a deck's branch ids resolve; numbers otherwise), and the branch-name dataset in `Inputs/Branch Names/` (Aaron, 2026-09-17): `morning_update` adds names from each client's Charts workbook (Branch Results tab, the file matched to one client by name or by `charts_files.csv`) and from the ICS referrals pull (VIP branch table), never removing one; `client_map(id)` reads it back, Charts name first, and leaves a number unnamed when one source gives it two different names.
- `month_complete.py` — the one definition of a complete month (pull/generation date, and a trailing month below half its six-month median), per measure; import-safe. Every YoY, latest-month and trailing-window comparison in every program goes through it (Aaron, 2026-09-17).
- `rpe_env.py` — machine-local paths (`RPE_DATA_ROOT` → `inputs()` / `outputs()`), build scratch (`temp_dir`, removed at exit; `sweep_temp`, run first by every `build_client`, clears scratch a crashed build left in the temp folder — 2026-09-16, after ~180 GB of it filled C:) and
  `use_font()`, which registers the bundled fonts and RAISES instead of letting matplotlib
  substitute a missing face. Every chart renderer goes through it.
- `assets/` — `logo.png` (CSI|Velocity lockup), `csi_logo.png`, `summit_slide.pptx`.
  **`summit_slide.pptx` is the ONE Summit slide** (Aaron, 2026-09-11): every builder
  clones it, and `summit_date()` reads its printed date, so replacing the Summit is one
  file. It used to be two — ICS/MRPC stamped a flat `Velocity Executive Summit.jpg`
  while ARS/CashPlease carried their own copy in their template shells, so the slide
  could only be replaced with PowerPoint, and every 2026.09 deck went out naming a
  Summit that had already happened. Drop the new `.pptx` here (or at
  `Inputs/Summit/summit_slide.pptx`, which wins when present) and rebuild.
- `README.md` — build/ layout notes (incl. the SM-vs-MM revenue-model extractor notes).

**`build/ics_pipeline/`** — ICS pipeline: `build_ics_gen.py`, `ics_charts_gen.py`,
`ics_local_sheet.py` (builds the ICS client sheet from local files — referral export, current workbook, Charts Goals tab, direct-mail list — when there is no VIP sheet; `build_month` uses it only then, 2026-09-16), `ics_workbook_extract.py` (the quarterly step: populates a client JSON's workbook sections
from the ICS workbook — see **Cadence**), `data/` (per-client VIP ICS data — one folder per client; keep client-named).
**`build/mrpc_pipeline/`** — MRPC pipeline: `build_mrpc_gen.py`, `mrpc_charts_gen.py`, `setup_template.py` (one-time template bootstrap; needs `mrpc_template_base.pptx`, which is NOT in the repo — ask Aaron for it if the template must be rebuilt), `data/` (per-client VIP MRPC data).

**`templates/`** — ALL deck templates live here (consistent naming; passed to each builder as an arg).
- `ars_template.pptx`, `ics_template.pptx`, `mrpc_template.pptx` — the three stripped per-program shells the builders populate (cleaned + styled; "Union Financial" dummy client). **The only legitimate starting point for a build.**
- `multi-product_reference_deck.pptx` — combined ARS+ICS+MRPC reference (Union Financial demo, styled); source for re-materializing the stripped templates.
- `STYLE.md` — visual style guide (single source of truth). `TEMPLATES.md` — reference section map + template materialization.


**`validation/`** — `validate_deck.py` (pre-ship lint gate, 0 FAIL to ship), `qa_all.py`
(the full gate: every template + given decks, package integrity, layout drift), `layout_baseline.json` (the drift fingerprints — `--snapshot` to accept).
**`fonts/`** — Montserrat (headings) and Carlito (Calibri-metric, charts), both bundled and
embedded. `rpe_env.use_font` RAISES rather than let matplotlib substitute a missing face.

`archive/` and `dashboards/` are NOT in this repo — the initial import excluded them. They
live only in the pipeline data root. Nothing here references either.
