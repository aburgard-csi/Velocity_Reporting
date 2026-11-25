# Pipeline notes: the full text behind CLAUDE.md's rules

Moved verbatim from `CLAUDE.md` on 2026-11-25, when Aaron asked for a shorter CLAUDE.md. `CLAUDE.md` now states each rule in a sentence or two; this file keeps the sections those rules were condensed from, word for word: the reasons, the incidents, the full Inputs table and the per-program detail. Read the matching section here before changing the behaviour a rule describes, or when a rule needs its reason. When a rule changes, change it in `CLAUDE.md` and in the paragraph here. The dashboards and the source watch are in `docs/OPERATIONS-dashboards.md` and `docs/OPERATIONS-source-watch.md`; the file map is `docs/FILE-MAP.md`.

**Where this differs from CLAUDE.md, CLAUDE.md is current.** Known stale in the text below as of
2026-11-25 (kept word for word so the move can be checked; not yet corrected):

- "Three programs" and "used by ALL THREE programs": CashPlease is a fourth program with its own
  subagent and builder.
- Templates names three shells; `templates/cashplease_template.pptx` is a fourth.
- Combined decks says `qa_all.py` checks that the file "actually opens"; since the render test was removed
  (2026-09-11) it checks package integrity only.
- The "History" paragraph on `C:\Data Pipelines\RPE Pipeline` ("the sibling folder", "deliberate again as
  of 2026-09-09") predates the 2026-09-14 move to the share.
- The Cadence ICS row reads the workbook "from `Inputs/ARS & MRPC Reports/`"; the builder resolves it
  through `rpe_env.report_dirs()` (`Inputs/ICS Workbooks/`).
- Data sources by program names a per-session location with `Workbooks - ARS` / `Workbooks - ICS`
  folders and has no CashPlease line; inputs are in the `Inputs/` kind folders.
- "Five CSMs" may no longer be the count.

## Preamble (the opening of CLAUDE.md as it stood)

This project builds client Executive Review decks for three programs. Each program has
its own subagent and its own data sources. **Keep them separate** — never run one
program's logic while building another. Confusion between programs is the exact problem
this structure exists to prevent.

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
from those inputs by definition, and **each CSM's folder holds its own archive**,
`Outputs/<CSM>/_Archive/<id> <client>/`, with the newest superseded deck of each kind per client
per period (Aaron, 2026-10-15: "Move the Archive under each CSM's folder in outputs rather than
in the root Outputs folder"; it was `Outputs/_Archive/<CSM>/<id> <client>/` from 2026-09-15 and
flat `Outputs/Archive/` before, and the folders were moved on 2026-10-15). `promote_month` moves
older decks of the same period and kind to
`Outputs/<CSM>/_Archive/_older decks - delete after review/<id> <client>/` — never deletes them —
and never moves a hand-made PDF. `promote_month.client_folder` resolves the folder: an existing
one in the CSM's archive first, else one still under the root archive (left by an older copy of
the code), so a client is never split across two places. The folder name lives in
`rpe_env.ARCHIVE_DIRNAME`; its underscore keeps it above the decks in the CSM's folder.

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
| MRPCPM analyses, and Bradford's MRPCEnrollmentSummary weeklies (Aaron, 2026-10-19: each weekly lands with its program; `Inputs/Weekly Summaries/` is gone) | `Inputs/MRPC Analyses/` |
| ICS workbooks | `Inputs/ICS Workbooks/` |
| ICS Charts (mystery shops) | `Inputs/ICS Charts/` |
| CashPlease data: CashPleaseSummary weeklies and the weekly `ILS-DDA-Count-<YYYY-MM-DD>.txt` (Aaron, 2026-09-16) | `Inputs/CashPlease/` |
| CashPlease production settings (Velocity Product Settings Power BI app, one record per client) | `Inputs/Product Settings/<id>_cp_settings.json` |
| CashPlease marketing emails from Bradford's "CashPlease Marketing eMails" thread (Aaron, 2026-09-21): the monthly per-client data `<id>_<Client>_<MM.YYYY>_Loan_Marketing_Emails.csv` — the ONE `.csv` the mail step accepts — and the undated per-client `<id>_<Client>_Loan_Marketing_Emails.xlsx`. Newest month per client; `mail_sources.cp_marketing_parts` reads both names, and `watch_sources.PRUNE_ALSO_KINDS` is how prune reaches a folder no reader globs | `Inputs/CashPlease Marketing/` |
| ARS database code tables (product, Reg E, account status codes per client; written by `scripts/ars_code_tables.py` from a database export — the export's settings table holds plaintext FTP credentials and is never copied) | `Inputs/ARS Settings/ars_code_tables.json` |
| Client code sheets (product with its Personal/Business flag, account status, mail flag and Reg E mappings per client; saved by the data team, where a CSM's corrections land) | `Inputs/Code Sheets/` |
| Anything unrecognised (read, never written) | `Inputs/ARS & MRPC Reports/` |
| Files a person drops by hand, any kind (Aaron, 2026-11-10; swept by the 08:00 file get since 2026-11-19, see **Daily source watch**). Not an input folder: nothing reads it but the sweep. The name lives in `rpe_env.DROP_FOLDER_DIRNAME` | `-Drop Folder/` (at the root, beside `Inputs/`) |
| ICS detailed referral exports (`<id>_ics_detailed referral_v<N>.xls`), for a client with no VIP sheet (hand-landed, member-level, never scanned) | `Inputs/ICS Referrals/` |
| ICS direct-mail new-accounts lists | `Inputs/ICS Direct Mail/` |
| Branch names: `branch_names.csv` (one row per name a source gave a client's branch number, with first/last seen; kept by the morning source check) and `charts_files.csv` (Charts workbooks matched to a client id by hand) | `Inputs/Branch Names/` |
| Client logos (`<clientid>.png`) | `Inputs/Logos/` |
| The FDIC / NCUA market reference store the Transaction Intelligence competition-layers slides match against: eight public JSON tables (FDIC institutions, branches, call reports; NCUA institutions, branches, trade names, call reports; Census ZIP centroids) and `vintages.json`. No client data. Built and landed by `scripts/build_market_reference.py` on a PC with the VPN (Aaron, 2026-11-23); refreshed each NCUA quarter (`--quarter`). Without it the layers slides are skipped and the build log says the store is not available. `TI_REFERENCE_DIR` overrides | `Inputs/Market Reference/` |
| Monthly debit-card transaction files, one folder per client, **stored zipped**: `<original name>.zip`, one file each (Aaron, 2026-09-17). **They come from the CSM ODDD folders** (Aaron, 2026-10-20; James's issue #23): the data team ships each one INSIDE `<id>_ODDD.zip` beside the ODD member, or unzipped in a `<id>_ODDD/` folder, and `scripts/land_txn_files.py` copies every non-ODD member out as its own zip here, by the member's banner line (a member the banner calls a *Master File* is not a transaction file and is reported, not landed), leaving the extract whole. It is run by hand, not by the 08:00 watch (50-minute limit; a month is about 10 GB). No deck reads them yet; any reader goes through `rpe_env.txn_files()` / `open_txn()`, which take either form — four files a security agent refuses to let the share hold zipped are still raw, and read the same way. `scripts/zip_txn_files.py` zips raw arrivals (safe to re-run) | `Inputs/Txn Files/<id>/` |
| The ILS deposits extract, rolling 365 days, one per client: `<id>_<Client>_ILSDeposits_<yyyy.mm>.zip` holding one CSV of hashed_account, deposit_date, deposit_amount (James Gilmore, 2026-10-23). Read only by the Transaction Intelligence cut, which takes a client's OWN file (`ti/deposits_input.py`); not scanned by the watch | `Inputs/Deposits/` |
| The ILS client analysis share's small files, one folder per client number then one per data pull, dated the day it was run: `<id>/<yyyymmdd>/<id>_<kind>_<yyyymmdd>.<ext>` for the extracts (kind from a fixed list), the analysts' workbooks kept by name under `analysis/` (Aaron, 2026-11-06; `docs/ILS-ANALYSIS-INPUTS.md`, applied by `scripts/ils_analysis_inputs.py`). **The newest pull of each client on the analysts' review schedule is landed whole, each extract zipped as `<canonical name>.zip`** (Aaron, 2026-11-24; `scripts/land_ils_analysis.py`, its own task, never the 08:00 watch), with `_schedule/` holding the schedule snapshot and `pulls.json` (newest pull, landed kinds, current or not). Read through `scripts/ils_analysis_landed.py`, raw or zipped. Not scanned by the watch (its `--ils-analysis` step lists the share, never this folder) | `Inputs/ILS Analysis/` |
| The ILS pre-go-live extract, one folder per client: `<id>_<Client>_PreGL_<yyyymmdd>.csv` or `.xlsx`, with the vendor's MatrixValidation / IntegrityCheck dumps beside it (James Gilmore, 2026-10-27). Read only by `build/ils_pipeline/pgl_input.py`; not scanned by the watch | `Inputs/ILS PGL/<id>/` |
| The ILS kickoff one-time data extract, one folder per client: `<id>_OneTimeData_<yyyymmdd>.csv` or `.xlsx` (James Gilmore, 2026-10-27). Read only by `build/ils_pipeline/kickoff_input.py`; not scanned by the watch | `Inputs/ILS Kickoff/<id>/` |
| The clients' finished **ILS Program Analysis reviews**, one folder per client: `<id>/<id>-<yyyy.mm>-ILS-<Client> ILS Review.pdf` (Aaron, 2026-11-06: "put ILS review PDFs on the share"). `scripts/land_ils_reviews.py --from <the Clients library>` copies the newest review per client from its `ILS Delivery` folder (copy-only, an older review stays beside a newer one) and reads it into `Build Artifacts/ils_analysis/review_packs/<id>_ils_review.json`, so a CSM's PC reads the pack and parses no PDF; a review whose tables do not reconcile is landed and reported with no pack. Read only by Live Review's ILS section; not scanned by the watch | `Inputs/ILS Reviews/<id>/` |
| The REMS (Reg E Management Solution) responses report: the result of `sql/rems_responses_report.sql` (one row per client per month: responses, opt-ins, opt-in rate), saved by a person as `rems_responses <YYYY-MM-DD>.csv` (Aaron, 2026-11-03). It holds every client, so it feeds both a client's REMS section and the peer comparison. Read only by Live Review (`peer_pool.rems_rows`); not scanned by the watch | `Inputs/REMS/` |
| Clients' **GL data and NSF / OD performance tracking spreadsheets**, emailed to us (Aaron, 2026-11-03): a monthly GL sheet (`FSB Michigan GL.xlsx`) or the ILS "NSF Performance Tracking Workbook". `scripts/gl_data_ingest.py` folds them into **`gl_data.json` in this folder, one table for every client** (keyed by client id, a source per spreadsheet), and `--archive` moves each one that was placed on a client to `_Archive/<id> <client>/`; `aliases.json` maps a file name to a client when it does not start with the client number. Kept to validate our own figures against; not read by any deck yet; not scanned by the watch | `Inputs/GL Data/` |
| ICS / MRPC client sheets from the VIP dashboards | `Inputs/VIP Data/<PROGRAM>/<id>-<Name>/<id>_<program>.json` |
| Build evidence (figure sidecars) — NOT deliverables | `Build Artifacts/` |
| The peer reference: every figure any peer comparison uses, one row per client, program, metric and period, tagged (unit, definition, period basis, complete month, source file and date, consumers) and dated (Aaron, 2026-11-20). `peer_metrics_<YYYY-MM-DD>.csv`, `peer_metrics_latest.csv` and `manifest.json`, written by `scripts/build_peer_reference.py` through `rpe_env.peer_reference_dir()`; client numbers, no name fields. No deck reads it yet | `Peer Reference/` |
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

**One exception: a Transaction Intelligence build's mail lists (Aaron, 2026-11-23: "send those lists to
outputs, sort them into each CSM's folders with the other files").** They go out with the delivered TI deck
as `Outputs/<CSM>/<id>-<period>-TI-Lists/` (one CSV per financial-services category, the master list, the
review queue and the slide ledger), put there by `ars_launcher.ti_lists_to_outputs` and, for builds made
before that, `scripts/ti_lists_backfill.py`. They are account-level lists for the CSM to work from, which is
why they are deliverables and not bookkeeping. A superseded lists folder is archived like a deck, never
overwritten. Readers of decks are unaffected: `rpe_env.output_decks` matches files, never a folder.

**Output — ONE destination (Aaron, 2026-07-25), filed by CSM (Aaron, 2026-09-14).** Every
finished deck goes to `Outputs/<CSM>/` — e.g. `Outputs/Aaron Burgard/` — now that the project
covers all five CSMs' books. Program is still distinguished by the filename tag, not by
subfolder. Writers resolve the folder with `rpe_env.client_outputs(id)` (the CSM from
`<RPE_DATA_ROOT>/Client CSM List.csv`, else the CashPlease roster's CSM column, else
`Outputs/_Unassigned/` — never a guessed CSM); readers use `rpe_env.output_decks(pattern)`,
which lists every CSM folder's own files and the flat root but never an archive (`<CSM>/_Archive/`
is a subfolder it does not enter; a root `_Archive/` is skipped by name). Each CSM folder's
`_Archive/` keeps a folder per client (2026-10-15). This replaced both the old **Client Presentations** drop and
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

**A slide with no data is left out, and said so — never zeroed (Aaron, 2026-11-22: "skip a slide if it
doesn't have data").** This REPLACES "Missing source data is stated" and "Never drop slides automatically",
under which a slide whose data the extract did not carry stayed in the deck with a sentence saying so
(Brooks Bank's Responder Age Profile: "Date of birth is not carried in this client's data extract..."). Now:

- **The slide is not in the deck.** A 0%, an empty chart or a stand-in figure is still never drawn.
- **Never silent.** Each one is printed to the build log as `slide left out (no data): <title> - <why>`.
- **Where it applies today:**
  - the ARS Responder Age Profile with no DOB (dropped by title in `build_ars_gen` phase 2);
  - the MRPC Program to Date and Current Program Status slides when the weekly has no tab for the client;
  - CashPlease Loan Volume by Month when the workbook has no loans for the client;
  - a "How You Compare" slide with no measure that has five peers (`build/peer_slide.py`);
  - every opt-in ARS view (the James / Companion views and the test slides), which registers itself with
    `shapes.mark_no_data` and is dropped by `shapes.drop_no_data_slides` once every view is in.
- **A slide is only taken out with `shapes.drop_slide`.** It removes the list entry and the relationship, then
  renames the kept parts in order, so a slide added later never reuses a freed part name (the duplicate-part
  defect). The other way to leave a slide out is to never put it in the deck's order and let `strip_dead` remove
  it (CashPlease).
- **What did NOT change:**
  - Absent data is still a data-sourcing question first. If the data is carried somewhere else (Reg E in the
    workbook rather than the ODD), populate the slide from that source rather than leaving it out.
  - A tile or a caption inside a slide that does carry data still states its gap ("n/a", "not shown").
  - A failure to READ data (the peers' figures unreadable) is a build problem, drawn and failed by the gate,
    never quietly skipped.
  - A left-out month is stated on its slide as before.

Transaction Intelligence exception (James Gilmore, 2026-10-30, Sheila's 1798 slide review):
a TI slide whose builder declines for a client ("Not shown for this client: ...") is hidden from
that client's deck, and a TI chapter with every slide declined loses its divider and agenda row.
Nothing is silent: each hidden slide is logged and listed in `hidden_declined.json` beside the art
(`build_ti_gen.build`). The data-sourcing rule above still applies to why a slide declined.

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

**Writing style.** All client-facing text follows Aaron's writing rules, recorded
here in full rather than pointed at elsewhere. Banned words include: robust, comprehensive,
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
- **A month that collapses in the MIDDLE of an extract is left out too (2026-10-13).** Marine's Aug 2026
  NSF/OD (390 items against about 19,000) stopped being a trailing month when September loaded and passed as
  complete. `month_complete` now reports `interior` gaps (below half the baseline median, at most two months,
  followed by recovery); read `usable_months(months, result)`, never `months[:complete]`, so a gap is skipped.
  A fall that holds is a real change and is not a gap.
- A left-out month is STATED — on the slide ("Aug 2026 left out: incomplete in this
  extract.") and with its figures in the notes — never zeroed, never charted as a collapse,
  and its slide is never dropped. Status snapshots (Elig, Reg E, account status) are not
  activity and still read the snapshot month.
- **The NSF/OD "Items YTD YoY" and the "Spend YTD YoY" tiles are year to date against the prior
  year to date** (Aaron, 2026-10-12: "change this to YTD rather than month vs month"; "did you
  also update the YoY comparison for debit card spend?"): January through the last complete
  month, summed, over the same months a year earlier; the caption names both windows
  ("Jan–Sep 25 → Jan–Sep 26") and the notes carry both sums. Every month of both windows must
  be complete, else the tile reads n/a — never a partial sum passed off as a year. A new YoY
  tile follows the same rule. **When the series does not reach back to January of the prior
  year, the spend tile falls back to like for like** (Aaron, 2026-10-15, Brooks Bank, whose
  Key Trends start Feb 2025): the longest run of months ending at the last complete month that
  both years carry, at least three, labelled "Spend YoY, like for like" with the caption naming
  the window ("Feb–Sep 25 → Feb–Sep 26") — the `spend_trend` rule. Fewer than three matching
  months still reads n/a.
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
