# Retail Performance Engine — Deck Build Router

This project builds client Executive Review decks for three programs. Each program has
its own subagent and its own data sources. **Keep them separate** — never run one
program's logic while building another. Confusion between programs is the exact problem
this structure exists to prevent.

**Working here as a collaborator (not Aaron)?** Read `docs/COLLABORATORS.md` first: branches and pull requests, what not to run, and what to check before a PR.

## Routing

Identify the program from the request, then dispatch to the one matching subagent:

| Ask mentions… | Program | Subagent |
| --- | --- | --- |
| ARS, Account Revenue Solution, mailings, Lift Matrix, Reg E, debit take rate | ARS | `ars-deck` |
| ICS, Invitation Checking, referrals, mystery shop, ROI per account | ICS | `ics-deck` |
| MRPC, MyRewards Premium Cards, enrollments, Gold/Platinum tiers | MRPC | `mrpc-deck` |
| CashPlease, CP, small-dollar loans, loans per 1,000 DDAs | CashPlease | `cashplease-deck` |
| ILS analysis review, prep slides, matrix parameters / overrides | ILS prep (not an RPE build) | the `ils-prep-deck` skill |
| ILS pre-go-live (PGL), ILS kickoff, a client's field summary or ILS codes | ILS pre-go-live / kickoff — James's v5 engines, run from the ILS cards on a client's page in Sheila | no subagent: `build/ils_pipeline/` (read its `README.md`); Sheila's cards are `scripts/ils_ui.py` and `scripts/ils_runs.py` |
| Transaction Intelligence, the TI cut, a lens (ARS lens / ICS lens), a chapter, the v5 port, parity, the duplicates register | Transaction Intelligence — a SEPARATE presentation, never an RPE build and never a change to one | no subagent: `build/ars_pipeline/ti/`, by hand, after reading `ti/PORTING.md` and **Transaction Intelligence branches** in `docs/COLLABORATORS.md` |
| An Executive Summit one-pager, a Summit handout, the Key Performance Metrics page, Summit attendees | Executive Summit one-pager: hand-built for ATTENDING clients only, never an RPE build and never scheduled | no subagent: the `summit-one-pager` skill (`.claude/skills/summit-one-pager/`), which also records Aaron's corrections to these pages |
| An HTML Artifact or web page for CSI / Velocity: a guide, catalog, dashboard, report or comparison, or the Design Library | A shared page, not a deck | no subagent: the `velocity-artifact-design` skill (`.claude/skills/velocity-artifact-design/`), on top of the bundled `artifact-design` |

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
| ICS detailed referral exports (`<id>_ics_detailed referral_v<N>.xls`), for a client with no VIP sheet (hand-landed, member-level, never scanned) | `Inputs/ICS Referrals/` |
| ICS direct-mail new-accounts lists | `Inputs/ICS Direct Mail/` |
| Branch names: `branch_names.csv` (one row per name a source gave a client's branch number, with first/last seen; kept by the morning source check) and `charts_files.csv` (Charts workbooks matched to a client id by hand) | `Inputs/Branch Names/` |
| Client logos (`<clientid>.png`) | `Inputs/Logos/` |
| Monthly debit-card transaction files, one folder per client, **stored zipped**: `<original name>.zip`, one file each (Aaron, 2026-09-17). **They come from the CSM ODDD folders** (Aaron, 2026-10-20; James's issue #23): the data team ships each one INSIDE `<id>_ODDD.zip` beside the ODD member, or unzipped in a `<id>_ODDD/` folder, and `scripts/land_txn_files.py` copies every non-ODD member out as its own zip here, by the member's banner line (a member the banner calls a *Master File* is not a transaction file and is reported, not landed), leaving the extract whole. It is run by hand, not by the 08:00 watch (50-minute limit; a month is about 10 GB). No deck reads them yet; any reader goes through `rpe_env.txn_files()` / `open_txn()`, which take either form — four files a security agent refuses to let the share hold zipped are still raw, and read the same way. `scripts/zip_txn_files.py` zips raw arrivals (safe to re-run) | `Inputs/Txn Files/<id>/` |
| The ILS deposits extract, rolling 365 days, one per client: `<id>_<Client>_ILSDeposits_<yyyy.mm>.zip` holding one CSV of hashed_account, deposit_date, deposit_amount (James Gilmore, 2026-10-23). Read only by the Transaction Intelligence cut, which takes a client's OWN file (`ti/deposits_input.py`); not scanned by the watch | `Inputs/Deposits/` |
| The ILS pre-go-live extract, one folder per client: `<id>_<Client>_PreGL_<yyyymmdd>.csv` or `.xlsx`, with the vendor's MatrixValidation / IntegrityCheck dumps beside it (James Gilmore, 2026-10-27). Read only by `build/ils_pipeline/pgl_input.py`; not scanned by the watch | `Inputs/ILS PGL/<id>/` |
| The ILS kickoff one-time data extract, one folder per client: `<id>_OneTimeData_<yyyymmdd>.csv` or `.xlsx` (James Gilmore, 2026-10-27). Read only by `build/ils_pipeline/kickoff_input.py`; not scanned by the watch | `Inputs/ILS Kickoff/<id>/` |
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

**Missing source data is stated, never zeroed.** If a field the deck needs is absent from the
extract (e.g. an all-blank `DOB` column → no age profile), the builder writes a plain sentence
saying the data isn't carried in this extract and flags it — it does not render a 0% or an
empty chart, and it does not drop the slide.

**Never drop slides automatically.** The deck keeps its full slide set. If a section's
data looks absent in one source — e.g. Reg E not present in the ODD dump — that is a
data-sourcing task, not a reason to remove the slide: populate it from the correct
source (workbook / core / VIP) or flag it for Aaron. Do not silently omit slides and do
not report a phantom 0%.

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
**The watch's landing record also counts as the source saying so** (2026-10-13): when the
share no longer holds this period's file but `source_watch.json` recorded an ODDD landing
for this client and period whose size matches the copy, `deck_status.watch_landing` vouches
for it (1539 Marine's October extract was taken back off the share a week after the watch
copied it, and Sheila called the copy "previous month"). **So does the extract's own pull stamp**
(2026-10-13, 1509 Texas Bay: an extract that came by email and was copied into Inputs by hand):
`deck_status.odd_stamp_period` reads the member file's `(MMDDYY_HHMMSS)` stamp, and a pull in the
cycle's month is that cycle's extract. A stamp naming another month is stale and says which; no
share copy, no watch record and no stamp is the stale case it always was.

**ICS workbooks arrive by email, not on the share (Aaron, 2026-08-31).** They
have no source-side signal, so their source column is `n/a` and a missing one
does not block — without a workbook for the period the ICS section builds
referrals-only, which is a valid deck.

### Daily source watch

```
python scripts/watch_sources.py [--notify] [--dry-run] [--period 2026.09 ...]
python scripts/watch_sources.py --check-stale     # has the daily watch been running?
powershell -ExecutionPolicy Bypass -File scripts\register_watch_task.ps1 \
        [-Time 08:00] [-Repo <checkout>] [-RetryHours 0] [-Unregister]
```

`deck_status.py` answers "is it there now"; `watch_sources.py` answers "what landed since I last
looked" (Aaron, 2026-09-08). It scans this month's and last month's folders on the CSI shares — ODD
extracts in all five CSMs' folders on `Velocity_company`, DCOs / ARS workbooks / MRPCPM analyses on
`Velocity_clientreports` — diffs the inventory against the last one, and reports files that are new,
re-landed (same name, new bytes) or gone, roster clients first. State lives in `Build Artifacts/`
(`source_watch.json`, `.log`, `_latest.md`, `source_watch_runs.json`). Share roots and their
`RPE_SRC_*` overrides come from `deck_status`. The full account — the incidents behind each rule,
the registration history and the watchdog's record — is in
[`docs/OPERATIONS-source-watch.md`](docs/OPERATIONS-source-watch.md); the rules that matter when
touching this code are here.

**Scheduling**
- **The file-get runs ONCE a day, at 08:00, and no more (Aaron, 2026-10-05).** Do not start a
  hand-run beside it: two copiers writing the same `Inputs/` folder produced a duplicate. The one
  sanctioned second fire is the watchdog's retry, on a morning the 08:00 fire never executed.
- The task is **"RPE Source Watch"**, run as the logged-on user (the share needs those credentials,
  the toast needs a desktop), with a 50-minute execution limit. `-Repo` targets a checkout other
  than the script's own — a worktree has no `.venv` or `.env` and cannot host the task.
- **Off VPN it exits 2 and leaves the saved inventory alone**; saving an empty one would make every
  file "new" the next morning. The scan's report, log block and inventory are saved BEFORE the copy
  and the steps after it, so a run killed part way still leaves its scan.

**Health is checked from OUTSIDE the watch.** A run that never executed writes nothing, so the
watch cannot report on itself — do not "simplify" this by having it check its own health.
`watch_sources.run_health()` reads the run record (`ok` / `stale` / `never`, by last FINISH,
outcome ignored); `refresh_performance_dashboard.py` prints it at 08:30 and the delivery dashboard
banners it; `--check-stale` scans nothing and answers off VPN. The **"RPE Source Watch Watchdog"**
task (`scripts/watch_task_watchdog.ps1`, **one fire a day at 08:10**, Aaron 2026-10-15: "I want this
running only at 8am or manually"; it was 08:20 and every 30 minutes for four hours from 2026-09-21,
which on a morning off the VPN logged "needs a human look" every half hour into the afternoon) asks
`--check-today`, and if no run has reached the shares it kills a fire Windows created suspended
and retries the main task, appending to `Build Artifacts/source_watch_watchdog.log`. It stays
(Aaron, 2026-10-05). A later check is a hand run: `Start-ScheduledTask -TaskName "RPE Source Watch
Watchdog"`, or the script itself; `register_watchdog_task.ps1 -RepeatHours 4` restores the old window. **A `watch_sources.py` process older than `MaxAgeSecondsAlive` (3 h) is
stuck whatever its counters say** (Aaron, 2026-10-07): a run that reached the shares and then
hung looks healthy, and the task is `MultipleInstances IgnoreNew`, so the next 08:00 fire is
dropped while it lives — the watchdog clears one even on a morning whose run did reach the
shares. A morning that logs "needs a human look" is the human look: check for a `pythonw.exe`
with 0 CPU and 0 handles, or one from yesterday, by hand.

**Copy (`--copy`)**
- Every file for **every client except a stopped one** (`clients.md` skipped rows) that `Inputs/`
  lacks or holds a different landing of is copied — all five CSMs' ODD folders, which each name
  month folders differently (`deck_status.odd_folder_period` is the one reader). `clients.md`
  decides what gets BUILT; the copy only decides what is on hand.
- **The ODD extract is copied only from the newest month on the share** for that client
  (`copy_plan`; `tests/test_watch_sources.py` pins it) — the local copy carries no period in its
  name, so copying last month's back would be the stale-ODD failure.
- **A "differs" file is overwritten only when the SOURCE is the newer write.** A workbook opened and
  saved in Excel so its formulas carry values is a deliberate change. A workbook that lands with
  unevaluated formulas reads as 1 month, 0 mailings, $0; `build/ars_pipeline/base_guard.py` stops
  every ARS entry point with `UNEVALUATED WORKBOOK` (open it in Excel, save, rebuild).
- Copy-only — a copy never deletes. A `.part` file is renamed over the target and the size verified.
  Small files first (`_copy_order`): every DCO, workbook and analysis before any extract, extracts
  smallest first, so a cut-short run never leaves a workbook waiting behind an extract.
- **An extract the share refuses as a zip is re-landed as its ODD member alone** (2026-10-13, 1815
  FedChoice): a security agent on the share deletes a zipped extract that carries the data team's
  monthly transaction file the instant it is written, under any name, with no error — the copy
  "succeeded", the `.part` was gone, and three mornings logged "size mismatch after copy" while
  Inputs kept September's extract. The raw CSVs and a zip of the ODD member alone are held.
  `_land_odd_member_only` writes the ODD member(s) into a new zip with their original entries (the
  pull stamp is unchanged), the record carries `reduced`, and the report says what was left out.
  Every deck reads only the ODD member; the transaction member feeds one opt-in James view. A
  workbook mismatch is never reduced.
- One unreachable CSM folder counts as off VPN.

**Prune (`--prune`).** A workbook-ish file in `Inputs/` is deleted only when a NEWER version of the
same client id and kind (or the same weekly family, later stamp) is present and non-empty. The
newest of each group is always kept, a lone file is never touched however old, files with the same
version key are ambiguous and both stay, and ODD extracts and ICS Charts workbooks are left alone
(`prune_plan`; tests pin it). The delivery dashboard's input columns for a PAST period therefore
read "not copied" once its inputs are pruned.

**Mail (`--mail`, `scripts/mail_sources.py`).** Bradford Sanders' MRPC and CashPlease reports and
CashPlease marketing emails, and Matt Milliman's ICS workbooks, come from Outlook and are filed by
kind with everything else.
- Outlook COM as the logged-on user, **read-only** (nothing marked read, moved, deleted or replied
  to). An unreachable mailbox is reported and skipped, never fatal.
- **The mail step cannot hang the run**: share results are saved BEFORE it, it runs as its own
  process (`watch_sources.mail_step`, `MAIL_TIMEOUT` = 10 min) and a timeout is reported;
  `mail_sources._outlook()` tries `GetActiveObject` before `Dispatch` because the latter can block.
  **The child writes to FILES, never pipes, and a timeout kills its whole process tree**
  (`_kill_tree`, `taskkill /T`; 2026-10-07): the endpoint agent relaunches each python start
  under the first, a relaunch left suspended inherits the pipe, and `subprocess.run(timeout=)`
  killed only the child and then read that pipe to an end that never came — the run hung for
  hours on 2026-10-05 and -06. Do not hand a child `subprocess.PIPE` with a timeout anywhere here.
- Senders are matched on the resolved SMTP address, and each sender may supply only their own
  kinds. Scan Inbox AND Archive plus subfolders; keep only the newest of each thing; an attachment
  whose name does not match `<id>-<period>-<kind>` is parked in the legacy folder and reported,
  never guessed at.

**ICS referrals (`--ics-referrals`, `--branch-names`).** `scripts/ics_referrals_pull.py` merges
each saved all-clients referrals query result into `ics_referrals.csv` (a referral = client,
account, issue date; a newer pull replaces the older rows) and rewrites the query's `@since` to the
day of the newest referral merged, so windows overlap on purpose and a skipped day widens the next
one rather than leaving a gap. `--branch-names` then adds new branch names from the Charts
workbooks and that pull to `Inputs/Branch Names/branch_names.csv`.

**Issue reports (`--issues`, Aaron, 2026-10-05).** `issue_reports.sync()` files every report queued
from CSM Sheila and refreshes the issue list its **Feedback** tab reads. It runs here because `gh`
is authenticated on this machine only; a morning with no `gh` or internet leaves reports queued.

Because the copy happens before the 08:30 dashboard refresh, a new month's workbooks reaching
`Inputs/` roll the performance artifact forward the same morning. `--notify` raises a toast only
when there is news or the shares were unreachable.

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
calendar month (Aaron, 2026-10-02).** It used to be the newest ARS workbook in `Inputs/`,
which left the page reading "Reporting period 2026.09" on 2 October while that month's
workbooks were still landing. **Within that cycle every client shows its own newest figures**
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
  invisible-retention-line fix out of the file entirely. **Every entry starts with a
  `Summary:` line** — one or two plain sentences saying what changed, for a CSM (2026-09-25).
  CSM Sheila shows that line in What's new and on its change log page, and leaves out the
  quoted request and inline "(Aaron, …)" attributions, which stay here as the record.
- `requirements.txt`, `.env.example` — runtime deps; `RPE_DATA_ROOT` and friends.
- `VERSION` — CSM Sheila's version (first line, `N.N`), shown in her header and copied by the release (Aaron, 2026-10-26: starts at 2.0). Bump it by hand in the commit that adds a major feature; `RELEASE.txt` still names the date and commit of each release.
- `docs/COLLABORATORS.md` — what a collaborator's Claude Code session needs: branches and PRs, what not to run, pre-PR checks.
- `docs/` — the PRDs: `PRD-2026-08-26-repo-portability-and-response-rates.md`,
  `PRD-2026-09-11-rpe-client-performance-artifact.md` (the cross-client performance page:
  what it is for, where each figure comes from, and why the script never publishes).
  `ILS-schema.md` — the hosted ILS database: every table's columns (names only, no sample
  rows), the join keys, the account-type / Reg E / status code values, and what Aaron has
  confirmed (`DELETED IS NULL` = in the current import; `ODCustomer` = access to the OD
  program, not usage). **Read it before writing any ILS query.**
- `sql/` — ILS queries a person runs in a client's ILS database; Claude cannot reach it.
  `ils_od_lookup_by_last4.sql` takes a customer list (raw account numbers, which cannot be
  matched to `HASHED_ACCOUNT`) and returns OD usage and the OD limit before an account
  number change and now. Customer lists and results never go in the repo.

**`scripts/`**
- `oddd_optimize.py` — raw ODD → data pack (`oddd_pack.md` + `oddd_metrics.json`); Reg E / account-status classifiers, funnel, mix.
- `build_month.py` — builds the monthly ARS/ICS/MRPC reviews for one period from the `clients.md` roster, `--jobs` clients at once (default 3; the share's ~3 MB/s is the limit). Never emits Summit one-pagers. `read_roster` adds **CP** to a client's programs when the CashPlease roster says their slides ship as a *section* (2026-10-12 — until then nothing read that column, so no CashPlease section was ever built here and 1632 / 1734 came out as plain ICS decks); a standalone CashPlease module is `build_cashplease.py`'s. Stages into a folder; `promote_month.py --apply` delivers.
- `deck_status.py` — the status engine behind the dashboard: for one period, what data has landed, what has been built, and what has been sent. Reuses `build_month.read_roster` so there is one answer to who gets a deck.
- `dashboard.py` — the local delivery dashboard (see **Delivery dashboard**).
- `ics_referrals_pull.py` — the `--ics-referrals` step: merges each ICS referrals query result saved as `Inputs/ICS Referrals/ics_referrals <date>.csv` into one `ics_referrals.csv` (a referral = client, account, issue date; a newer pull replaces an older pull's rows for the same referral) and rewrites `ICS Referrals - new since last pull.sql` beside it with `@since` = the day of the newest referral merged. The query itself (`sql/ics_referrals_all_clients.sql`) is run by a person; Claude cannot reach that database.
- `ils_dda_count_mail.py` — saves the newest "ILS Management Server DDA Count" email body (Charles Baker's weekly forward) word for word from Outlook as `Inputs/CashPlease/ILS-DDA-Count-<sent date>.txt`, the CashPlease loans-per-DDA denominator. Run by the CSI Email Monitor task (`C:\Data Pipelines\Email Pipeline\run-monitor.ps1`) before its Claude step (Aaron, 2026-09-17); never overwrites a saved week whose table differs.
- `mail_sources.py` — the `--mail` step: reads Bradford's and Matt's attachments out of Outlook via COM, files them by kind, newest-only (see **Daily source watch**). `.xlsx`/`.xlsm` only, except the CashPlease marketing CSVs (`CSV_KINDS`).
- `watch_task_watchdog.ps1` — detects a "RPE Source Watch" run Windows created suspended and never executed, kills it, and retries (see `docs/OPERATIONS-source-watch.md`).
- `register_watchdog_task.ps1` — registers / removes the Windows scheduled task "RPE Source Watch Watchdog" that runs it.
- `watch_sources.py` — the daily CSI-share check: what ODDD / DCO / workbook files landed since the last run, with local-copy state (see **Daily source watch**). Also keeps the run record and answers `--check-stale`.
- `register_watch_task.ps1` — registers / removes the Windows scheduled task "RPE Source Watch" that runs it daily, one fire at 08:00 (`-RetryHours 4` restores the old morning retry window). `-Repo` targets a checkout other than its own.
- `refresh_performance_dashboard.py` — rebuilds the "RPE Client Performance" artifact's dataset and page into `Build Artifacts/perf_dashboard/`, with change detection against the last published hash (see **The performance dashboard artifact**).
- `perf_dashboard_template.html` — that artifact's page, with a `__DATA__` slot the refresh script fills. Edit here, never in the published copy.
- `ars_launcher.py` — builds one client's deck: an ARS client's ARS deck, or with `--combined` one deck with ARS plus every other program whose data is on hand; **a client with no ARS builds the one deck their programs make** — ICS, MRPC, the standalone CashPlease module, or any mix of ICS, MRPC and CP — from every program with data, checked on each program's own data and none of the ARS rules (Aaron, 2026-10-13: "bring CP only, ICS only, and MRPC only decks into Sheila, also any combination of those"; `client_entry`, `build_programs`, `cashplease_availability(standalone=True)`) (`program_availability`: ICS from VIP or the local ICS files, MRPC from VIP, **CashPlease from its own roster table in clients.md** — not the main roster row, which does not carry it; only a row that ships CP as a SECTION joins the deck, and CP is last in section order, Aaron 2026-10-02). **CashPlease is on the PLAIN build too** (Aaron, 2026-10-12, "add the CashPlease slides into Sheila decks"): `build_programs` makes every build's program list — ARS, plus CP for a client who ships it as a section, plus ICS/MRPC only when `--combined` — so a CSM choosing the first button for 1192 Ascend gets ARS-CP, never an ARS deck with the CashPlease section missing), into Outputs without Claude (`status | build <id> [--combined]`): checks the product list, `clients.md`, the combined-deck rule, sent state and input currency first, works in `Build Artifacts/launcher/<period>/<id>/`, and puts a 0-FAIL deck straight into `Outputs/<CSM>/`, archiving what it supersedes. No staging step: each CSM reviews, PDFs and emails the deck from Outputs (Aaron, 2026-09-15). **`build <id> --ti` builds the Transaction Intelligence decks instead** (Aaron, 2026-10-23): a separate presentation, one deck per lens, checked by `ti_checks` and filed by `ti_to_outputs` beside the RPE deck, never in its place; `status <id> --ti` shows those checks; the record is `_launcher_result_ti.json`.
- `ars_launcher_web.py` — CSM Sheila, the Smart Helper for Executive Insights, Layouts & Analytics (was ARS Deck Builder until 2026-09-16, then briefly WILL), the browser front end for `ars_launcher.py`: a 127.0.0.1-only server whose page lists every client with a deck to build — the whole `clients.md` roster in any program mix plus the standalone CashPlease module clients (2026-10-13), each with pills for the programs its deck covers and the client's other Velocity products — shows the launcher's checks and runs `ars_launcher.py build` as a child process, streaming its steps. A client with no ARS gets one button, named for the programs with data (`builds_on_offer`). Builds run one at a time; one asked for while another runs waits in a first-in, first-out queue, the client page offers "Build ARS only" and, when another program has data, "Build combined (ARS + …)" (Aaron's multi-program clients get only the combined one), and the list shows Building / Queued #N, or a red Error <period> pill when the client's last build was not put in Outputs (its button then reads Retry build). Every API call needs the token baked into the page and a localhost Host header; "Show in File Explorer" opens only a file under Outputs. A **Data Issues** tab (2026-09-25) shows each client's issues from `issue_pages/gaps.json`, `issue_pages/odd_findings.json` (2026-10-02) and the morning dashboard's `actions` (unmapped codes, Lift Matrix flags), each dated, and any item can be marked complete (`Build Artifacts/issue_pages/done.json`) until a newer ARS / MRPCPM / ICS workbook lands for the client (2026-09-28); every client page links its newest code sheet in `Inputs/Code Sheets` (opened by Sheila, found by client number). A **Lift Matrix** tab (2026-09-25) lists every ARS client's current workbook matrix beside the one `lift_values` calculates from its ODD, side by side with the change and each segment's step, both lift grids, the IC rate, NSF/OD fee, OD collection rate and outlier cap editable and applied by **Recalculate**; **Export this matrix** records the export in `Build Artifacts/lift_values/<id>-<period>-exported.json` and downloads the Excel file for Bradford (never written to Outputs); each ODD is read once in the background and kept in `Build Artifacts/lift_values/`, and each workbook's Lift Matrix is read again only when the file's size or modified time changes (`workbooks.json` there, shared by every copy of Sheila). The header shows the five newest CHANGELOG.md entries and links the full log (`/changelog`). **It serves from memory and refreshes behind the page (2026-09-17):** the client list is rebuilt in the background when it is older than `CLIENTS_TTL` (60 s), on "Refresh", or when a build finishes, and the page shows its age ("List as of …") and the last list it had (sessionStorage) while loading; builds this server ran (Building, Queued, Error, the deck put in Outputs) and Lift Matrix tags are laid over the stored list on every request. A client's status older than `STATUS_TTL` (600 s) is shown at once, marked "checking again", with its Build buttons held until the fresh check arrives; "Check again" is always a fresh read, and a client whose list row changes (deck, sent, last build) has its status dropped. Repeated share questions (reachability, report folders, VIP manifest, cycle period, the CSM list row) are kept for `SHARE_TTL` (60 s) by `install_share_caches()`, which only `main()` installs: `ars_launcher.py build` runs as its own process and its pre-build checks never see these caches. It decides nothing itself. **The client page's Transaction Intelligence panel** (2026-10-23) shows `ars_launcher.ti_status` for an ARS client — its own checks, verdict, last build and a button that runs `build --ti` through the same one-at-a-time queue — under the Executive Review's; the list shows a "TI in Outputs" chip, kept apart from "In Outputs". The status is cached with the client's (`STATUS_TTL`), and its share reads (`rpe_env.txn_files`) for `SHARE_TTL`.
- `sheila_mcp/` — **Sheila in Claude** (James Gilmore, 2026-10-30): CSM Sheila as a Claude Desktop connector for every CSM, "built once, no csm has to do it". `python -m sheila_mcp` serves the MCP stdio protocol with the standard library (`stdio.py`; no SDK, so the Python runtime is unchanged). Its tools (`__main__.py`; the answers in `core.py` and `actions.py`) call the same `ars_launcher_web` / `ils_runs` functions the page's buttons call, never copies of them: `my_month`, `clients`, `client_status`, `build` (refuses a blocked client; replaces a deck in Outputs only with `confirm=true` after the CSM's yes), `build_progress`, `build_queue`, `deck_summary`, `review` (the validator's report kept beside each built deck as `<deck>.pptx.validation.txt` by `ars_launcher.run_validator`), `explain` (a slide's figures and the source its notes name), `outputs`, `data_issues`, `ils_status` / `ils_run` / `ils_progress` (step 1 field summary; codes are the CSM's call), `whats_new`; and from `reports.py`, reading only the share: `cashplease_report` / `cashplease_portfolio` (the CashPlease build's packs), `peer_compare` (every client's launcher `metrics.json` for the cycle), `one_pager`, `client_brief`, `client_prepare` (with `perf_dashboard/dataset.json`; notes, tasks, calendar and mail are the CSM's own Microsoft 365, not Sheila's). Who is asking is the Windows user read as a CSM name (`who.py`). Builds from either door take `%LOCALAPPDATA%\RPE\build.lock` (`ars_launcher_web._take_build_lock`), so one runs at a time per PC. Delivery is a **Claude Desktop extension, never the launcher** (James Gilmore, 2026-10-30: "none of this should be in the sheila.bat gui"): the release runs `sheila_mcp/pack_extension.py`, which writes `CSM Sheila.mcpb` to the CSM_Reporting root (MCPB manifest 0.3, `binary` server, Windows only; version from `VERSION`, tool list read from the `@mcp.tool` functions in `__main__.py`). A CSM installs it once in Claude (Settings → Extensions, or by opening the file). It carries no Sheila code: `extension/server/sheila.cmd` (started as `cmd /d /c`) runs the share's `runtime.cmd` with stdin from nul and output to stderr (stdout is the protocol), then serves `python -m sheila_mcp` from `%LOCALAPPDATA%\RPE\Code`; the share folder is the extension's one setting (`csm_reporting_folder`, default `M:\CSM_Reporting`). `runtime.cmd` and the launcher .bat files never touch Claude. `legacy.py`, run by `sheila.cmd` before serving, removes the `sheila` entry the launcher wrote into `claude_desktop_config.json` for a few hours on 2026-10-30 (only an entry whose script is `sheila_start.py`; `.bak` kept), so Claude never runs two Sheilas. Tests: `tests/test_sheila_mcp.py`.
- `issue_reports.py` — issues reported from CSM Sheila (Aaron, 2026-10-02). The button QUEUES
  to `Build Artifacts/issue_reports/` and never calls GitHub: Sheila runs on each CSM's machine
  from the share and the repo is private, so a token in `Tools\\RPE` would be readable by
  everyone. `sync` (run where `gh` is authenticated — Aaron's machine) files each queued report
  and writes `gh issue list` back as `issues.json`; `view` merges the queue with that cache for
  Sheila's **Feedback** tab. A report that cannot be filed STAYS queued, sync is idempotent, and
  the `sheila` label is created if the repo has not got one.
- `slide_votes.py`, `slide_review_ui.py` — **Slide Review** (Aaron, 2026-10-27; made program-level 2026-10-28): CSMs vote Keep / Delete / Appendix, and star favorites, on each PROGRAM's slides (ARS, ICS, MRPC, CashPlease, Transaction Intelligence, ARS Companion) — **not tied to a client**, so a CSM can open Sheila beside any deck. A program's slide list is the build itself, never a deck (Aaron, 2026-10-29): `build/slide_inventory.py` reads each template shell and splices in the slides its builder adds where the builder anchors them, the Transaction Intelligence register (`ti/slides.json`) and the Companion's view titles; cover, agenda, dividers, Questions and Contact are not voted on. (`slide_votes.deck_slides` still splits a deck into programs at each divider, for the first-round votes and the tests.) A vote is one JSON file in `Build Artifacts/slide_votes/` (never a shared file several CSMs write back) carrying the voter's whole state for the slide (vote, star, comment); the newest per voter and slide wins, and a slide is its TITLE with any client's name and figures taken out — never its number. `slide_votes` is the record and the counting (import-safe); `slide_review_ui` is the tab's style and script, spliced into Sheila's page by `install`, which raises when an anchor in the page has moved. The Summary counts keep / delete / appendix / stars per program and exports CSV. First-round votes (per client) are still read: a single-program deck's maps to its program. `tests/test_slide_votes.py` pins it.
- `launchers/` — `Build ARS Deck CLI.bat`, `ARS Deck Builder GUI.bat` (starts `ars_launcher_web.py`), `ARS Deck User Guide.html` (released to the CSM_Reporting root) and `runtime.cmd`, which unpacks the released Python to `%LOCALAPPDATA%\RPE` on first use and copies `Tools\RPE` to `%LOCALAPPDATA%\RPE\Code` whenever a new release is stamped (`RELEASE.txt`); the .bat files run the code from that local copy, never from the share (2026-10-06: a build run from the share took over an hour in imports alone).
- `.claude/skills/summit-one-pager/` — the checklist for an Executive Summit one-pager (Aaron, 2026-10-28): attendees named by Aaron, figures shown unranked, his say on the story, then, for the multi-program **Key Performance Metrics page** (Fort Lauderdale 2026), `kpm_page.py` and `kpm_charts.py` beside it on the brand template in `assets/` (a JSON spec per attendee, every figure verified against the newest reports, rendered and looked at, saved to OneDrive `Executive Summits\<yyyy> <City>\`), or `build_ars_onepager.py` for the older ARS-only page. Aaron's standing corrections to these pages are recorded in the skill's Standards section (2026-10-30: build through the skill and keep it updated). `tests/test_summit_kpm_page.py`. Not a schedule and not in `build_month`.
- `.claude/skills/velocity-artifact-design/` — how a Velocity HTML Artifact looks (Aaron, 2026-11-02): the Apple-style page system in `assets/velocity-page.css`, the brand values to take from `build/brand.py` (CSI Orange `#F15D22`), multi-page artifacts, and how to render and check a page before publishing. It is the house look for the Velocity Design Library (Brand Guide, Chart Catalog, James vs Aaron). Not a deck and not part of the pipeline.
- `release_launcher.ps1` — copies the code to `<root>\Tools\RPE` and the .bat files to the root; `-Runtime` also ships the zipped Python. **The launcher runs the released copy: re-run after any change, `clients.md` included.** **A release ships origin/main and nothing else (Aaron, 2026-10-07; the default since 2026-10-08):** by default it fetches `origin/main`, checks it out detached into its own release worktree (`%LOCALAPPDATA%\RPE\release-worktree`, kept between runs so robocopy copies only what changed) and releases that — whatever is half-done in a checkout never reaches the share (a 2026-10-07 release from the working tree carried another session's unfinished file). `-FromWorkingTree` releases this checkout instead and refuses a dirty tree or a HEAD not on `origin/main` unless `-Force` is added, which stamps `RELEASE.txt` `FORCED`. The `.venv` for `-Runtime` is always read from the real checkout. `tests/test_release_launcher.py` pins all of it.

**`.github/`** — the repo's own protection, now that it has several contributors (Aaron, 2026-10-07):
- `workflows/tests.yml` — the unit suite on every pull request and push to `main`, on a Windows runner, against an empty `RPE_DATA_ROOT` (tests that need the share skip). This is the status check a ruleset on `main` requires before a merge. No secrets, no share.
- `CODEOWNERS` — `build/`, `validation/`, `templates/`, `clients.md`, `CLAUDE.md`, `.github/` and the release and task-registration scripts request Aaron's review on every pull request that touches them.
- Branch protection itself (pull requests only, one approving review, no force-pushes or deletion, the `tests` check required) lives in the repo's ruleset on GitHub, not in a file; it needs GitHub Pro or an organization plan — a private repo on a Free personal account cannot protect a branch.
- `issue_pages/` — the two team issue pages, **ODD and Workbook Issues** (`https://claude.ai/artifact/7FAYo9SYuDQPMbqXyRbsKv`) and **CSM Data Gaps** (`https://claude.ai/artifact/KgWEVJxB6tC7EA6sbFjdvN`, published 2026-10-02 after the earlier artifact went missing) — published as Claude artifacts, copied to `Notes/`. Republish to these URLs; never create new ones. `build_issue_pages.py [--no-scan] [--no-notes]` runs the chain after `refresh_performance_dashboard.py`: `gaps_matrix.py` (per-client gaps -> gaps.json), `noprog_odd_dates.py`, `missing_wb_history.py` (every month on the reports share for the Missing Workbook clients), `business_flags.py` / `mail_flags.py` (full ODD scans; `--no-scan` reuses them), `odd_wb_by_csm.py` (the ODD page, with the Lift Matrix date check; it also writes `odd_findings.json`, its findings beyond gaps.json, which CSM Sheila's Data Issues tab reads beside gaps.json and the dashboard dataset, so one issue-pages run refreshes Sheila too), `gaps_inject.py` + `gaps_template.html` (the Data Gaps page). `clients_products.py <export.csv>` loads a new Velocity client/product export. Paths come from `common.py` via rpe_env; working data and pages live in `Build Artifacts/issue_pages/` because they carry client names and products. Publishing the artifacts needs Claude.
- `perf_workflow.html` — the page's linked "How the decks are made" page (inputs, outputs, folder map), published beside it as `workflow.html`.
- `perf_clients.py` — which clients the page lists: every current client on the reports share, with programs inferred for clients `clients.md` does not cover.
- `perf_overview.py` — the page's Client overview figures, and the per-client code counts, from each ODD extract (cached per extract).
- `perf_actions.py` — the page's CSM action items: Lift Matrix flags in workbook filenames, and ODD codes the client's ARS code tables do not list. Never maps a code; the CSM corrects the client's code sheet.
- `zip_txn_files.py` — zips each file in `Inputs/Txn Files/` to `<name>.zip` beside it, checks the zip's size and CRC against the original, then deletes the original (a refused delete is reported). Re-run it after landing new transaction files by hand.
- `land_txn_files.py` — collects the clients' monthly transaction files from every CSM's ODDD folder on the share into `Inputs/Txn Files/<id>/` (Aaron, 2026-10-20, for James's issue #23): every non-ODD member of `<id>_ODDD.zip`, and every non-ODD file in a `<id>_ODDD/` folder, for month folders from `--since` (default last month) on, each landed as `<member name>.zip` with its timestamp, verified (size, CRC, decompressed CRC, not emptied by the share) and written through a `.part`. A member whose banner line names something other than a transaction file (1121's September extract carried its DDA master file) is reported and left. Idempotent: a file on hand is skipped, one on hand at another size is reported, never overwritten; the source extract is never changed. Landings are logged to `Build Artifacts/txn_landings.json`. Hand-run (`--dry-run` first): not in the watch, whose 50-minute limit a month's files would overrun.
- `changelog_merge.py` — resolves a `CHANGELOG.md` merge conflict by keeping BOTH sides (every branch adds its entry at the top, so two branches always conflict there): markers removed, a blank line before every entry, line endings kept, entries with no `Summary:` line reported; refuses a file with no conflict or unpaired markers. Used by the `merge-and-release` skill (`.claude/skills/merge-and-release/SKILL.md`: merge a PR once CI passes, fix its conflict or failure, check `main`, release Sheila with `release_launcher.ps1`, tag the backup; nothing merges or releases without Aaron's word). `tests/test_roster_and_changelog_tools.py`.
- `roster_candidate.py` — read-only: the `clients.md` rows a client is missing, from the CSM list (programs, CSM), the newest ARS workbook (Path MM or SM, via `perf_clients.detect_path`) and the CashPlease pack (loans). Used by the `add-client-to-roster` skill (`.claude/skills/add-client-to-roster/SKILL.md`), written after 1585 was "missing" from Sheila for want of a row.
- `mail_strategy_facts.py` — the figures behind Aaron's **Delivery Call Notes** (2026-10-28), read-only: per client the programs, the last send (= Recent Review Date, from `deliveries.json`), ARS profitability (a phrase only below 3:1) and the ICS / MRPC / CashPlease lines, each the last COMPLETE month against the prior six months' average with the +/-20% band ("consistent with" / "higher than" / "lower than"; never % of goal), worded in one function. It never touches the Mail Strategy form: the project skill `.claude/skills/mail-strategy-notes/SKILL.md` drives that (Claude in Chrome on the Work Laptop, snapshot the month grid first, a table and a yes before filling, a yes before Submit, reload and compare after; ILS items are left out of these notes). `tests/test_mail_strategy_facts.py`.
- `ars_code_tables.py` — extracts ONLY the product, Reg E and status code tables from an ARS database export into `Inputs/ARS Settings/`; the settings table (plaintext credentials) is never parsed past its header.

**`build/ars_pipeline/` — the ARS pipeline (client-agnostic)**
- `build_ars_gen.py` — the ARS deck assembler: populates the `ars_template.pptx` shell, inserts Product Mix and Excluded Accounts, writes source notes, adds the Contact slide, moves the Appendix after Contact, restyles fonts, runs the logo/slide-number branding pass.
- `metrics_gen.py` — ~105 chart metrics from the ODD (streams the `.zip`).
- `charts_gen.py` — renders the 28 chart PNGs; `DIM` = each chart's pixel size (must match its slide box aspect).
- `chart_lib.py` — shared take-rate-by-branch renderer (personal orange / business navy; identical size).
- `base_tab_extract.py` — SM financials from the workbook (+ DCO).
- `xl_cache.py` — random cell access over a read-only workbook with each sheet read once (`ws.cell` on a read-only sheet re-streams it from the top); used by the three workbook extractors.
- `base_guard.py` — refuses a workbook whose formulas were never evaluated (extracts as 1 month, 0 mailings, $0); called by both extractors, the builder and the dashboard refresh.
- `extract_base_gen.py` / `extract_lift.py` — MM financials / Lift Matrix rows.
- `lift_window.py` — the ONE reading of the Lift Matrix MM window (Start/End Date, the data month, `in_window` / `data_past_end`), import-safe. `extract_lift` puts it in lift.json; `ars_launcher.lift_checks` stops an MM client's build when the data month is past the End Date or the workbook filename carries the data team's Lift Matrix flag.
- `lift_values.py` — a client's ARS Lift Matrix valued from its own ODD (Aaron, 2026-09-25): every ARS-eligible card-holding account, consumer and business — `POPULATION` at the top selects `both` (the default), `personal` or `business`, a blank `Business?` counting only under `both`, and the scan records the choice (Aaron, 2026-10-05) — in seven swipe segments, and NH valued independently on the eligible accounts with no card; the distribution is of every eligible account, NH included; 12 complete months, swipes rounded down into the band, spend and NSF/OD items capped at a percentile of each segment (`WINSOR_PCT` = 0.99, one of `WINSOR_OPTIONS`); IC rate from the workbook (else 60 BP), NSF/OD fee = the most common per-item `Fees1` value in the ODD (else the workbook's NSF Fee), collection 100%. Renders the file emailed to Bradford as `<id>-<yyyy.mm>-ARS-<Client> ARS Lift Matrix.xlsx`. CSM Sheila's Lift Matrix tab runs it; import-safe.
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
- `pnl_slide.py` — **ARS Financial Performance**, on every ARS deck (Aaron, 2026-10-02): the
  program's P&L from the workbook's Actuals tab — incremental revenue, each itemised cost line,
  total costs, incremental profit and profitability — for the last complete month, the year to
  date and the program to date, over a twelve-month chart of revenue split into cost and profit.
  Figures come from `revenue_guarantee_slide.pnl`, so this slide and the guarantee cannot
  disagree. **A ratio is printed by `revenue_guarantee_slide.ratio_text` and nowhere else, from
  the UNROUNDED quotient (2026-10-12):** the extractors stored `profitability` at two decimals
  and the divider printed `f"{2.15:.1f}"` = "2.1 : 1" under a P&L that printed 2.2 : 1 from the
  same True Sky figures. `validate_deck.ptd_ratio_findings` FAILs a deck that states the
  program-to-date ratio two ways. It is drawn IN PLACE over the template's slide of that name: nothing is added and
  nothing is dropped, because a freed partname gets handed to the next slide added (it removed
  Excluded Accounts from a build on 2026-10-02).
- `revenue_guarantee_slide.py` — the Revenue Guarantee slide, inserted after ARS Financial
  Performance: a P&L from the Actuals tab (revenue, each cost line, total costs, profit — last
  complete month and program to date; Aaron, 2026-10-02) beside the profitability callout, and
  either the surplus over the 2 : 1 guaranteed minimum or the gap with the months to cover it (the months account for cost accruing over
  those same months). Run rate reads complete months only. On EVERY ARS deck whose ratio is
  below 3 : 1 (Aaron, 2026-09-25) — not one of the opt-in James views.
- `combined_insights.py`, `insight_charts.py`, `combined_insight_slides.py` — the views from James
  Gilmore's deck, merged from `test/james-aaron-combined` 2026-09-17 and still OPT-IN:
  `build_ars_gen` adds them only when `RPE_JAMES_SLIDES=1`. The original six (revenue by mailing,
  responders vs mailed non-responders, card account health, take rate and Reg E by branch, Branch
  Scorecard with number and name, ARS scorecard) plus, from 2026-09-21: Revenue Build by Mailing,
  Where This Month's Revenue Came From, Revenue per 1,000 Offers, Where Take Rate Lags, Where
  Reg E Opt-In Lags, Swipe Tier Migration, PIN and Signature Mix, Overdraft Limits by Reg E
  Election, Responders vs Their Own Segment, Where the Balances Sit, and What Five Points Would
  Be Worth. **These are REVIEW slides**: each one's speaker notes carry its source, its method
  and its open issues in full (`_notes` in `combined_insight_slides`), which is why they are not
  worded for a client.
- `james_views.py`, `james_view_charts.py`, `james_view_slides.py` — the SECOND round of James
  views (Aaron, 2026-09-25: "add in as many as possible and then we'll edit down from the
  maximized copy"), same opt-in, reached through `combined_insights.compute` (`ci["more"]`) and
  `combined_insight_slides.add_insight_slides`: Revenue per Fee Dollar by Mailing, Offer Segments
  per 1,000 Mailed, Response by Offer Number, Responders vs Non-Responders by Mailing, What a
  Response Is Worth, Tier Movement by Response, First Swipes: Program and Organic, Where Card
  Spend Goes, How the Money Moves (the ODD zip's monthly transaction file), Where Cards Lag, What
  a Card and an Opt-In Earn, Value by Account Age, Accounts Under Stress, Branch Value per
  Account, Reg E Elections Over Time, Program Cascade, Where Accounts Close, Card Spend Before a
  Close. Money is priced only at the WORKBOOK's own Interchange Rate and NSF Fee
  (`lift_values.workbook_assumptions`); activity windows go through `month_complete`.

- `sustained_split.py`, `sustained_split_slide.py` — the ONE sustained-responder measure
  (`by_mailing`, also used by `metrics_gen`) split by offer, Non-User vs Threshold, and the
  opt-in test slide that shows it (`RPE_TEST_SLIDES=1` or `RPE_JAMES_SLIDES=1`; Aaron, 2026-10-02).
- `spend_trend.py`, `spend_trend_slides.py` — debit spend per cardholder (the workbook's Key Trends,
  the figure to quote), and from the ODD the SHAPE of it: cards in use each month, spend per card in
  use, spend per ARS-eligible account open in the month (Aaron, 2026-10-12, Brooks Bank). The
  comparison is **like for like**: the months of this year to date that the prior year also carries
  (a series starting Feb 2025 compares Feb–Sep with Feb–Sep; a full series Jan–Sep with Jan–Sep; a
  series with no prior-year month makes no comparison, stated). Wording follows the +/-2% band.
  Two slides after "Overall Debit Swipes & Spend", **opt-in** (`RPE_SPEND_SLIDES=1`; "we may include
  those permanently"). The ODD is today's book, so its history understates earlier months — the notes
  say so.

- `companion_deck.py` — the **ARS Companion deck** (Aaron, 2026-10-27: "Build functionality in Sheila (a new button) to build a ARS Companion Deck with James's slides"): James's analysis slides as a SEPARATE presentation beside the approved Executive Review, never changing it. `ars_launcher.py build <id> --companion` builds the ARS deck in its own staging folder (`Build Artifacts/launcher/<period>/<id>/companion/`) with every opt-in view on (`RPE_JAMES_SLIDES`, `RPE_SPEND_SLIDES`, `RPE_COMPANION`; `ars_launcher.COMPANION_ENV`); with `RPE_COMPANION=1` `build_ars_gen` records the ids of the slides those views added (`companion_slides.json` beside `metrics.json`), and `companion_deck.build` keeps only the cover (retitled "Executive Review Analysis • <month>", so `validate_deck._cover_client_and_month` still reads it), those slides, Questions & Discussion and Contact. Slides are only dropped, never added, so the freed-partname hazard does not arise. Validated like any deck (0 FAIL + package check) and filed by `ti_to_outputs` as `<id>-<yyyy.mm>-COMP-<Client> ARS Companion.pptx`: "COMP" is not a program tag, so `promote_month` never reads it as an ARS deck, `decks_in_outputs` never counts it as the period's RPE deck and an RPE build never archives it (`is_companion_deck`). `status <id> --companion` shows its checks (`companion_checks`: the client on ARS, this period's ODD extract, workbook, DCO and the Lift Matrix window); CSM Sheila's client page carries its own **ARS Companion** panel and button (`companionPanel`, `/api/build` with `companion`), a "Companion in Outputs" chip, and the same one-build-at-a-time queue. `tests/test_companion_deck.py` pins all of it.
- `build_ti_gen.py`, `ti/` — the **Transaction Intelligence cut** (James Gilmore, 2026-10-22): a
  SEPARATE deck, in an ARS lens and an ICS lens, for the transaction intelligence, competition,
  attrition and deposit analyses migrated one at a time from his ARS v5 engine. It never edits the
  ARS deck, its metrics or its template; an overlap with an existing slide is recorded, not
  replaced. `ti/cut.py` holds the lenses, the chapter list (`CHAPTERS`, resolved on first use from
  `ti/chapters/`, which imports `cut` for `Chapter`) and the file name `<id>-<yyyy.mm>-TI-<ARS|ICS>-<Client> Transaction
  Intelligence.pptx` — "TI" is not a program tag, so `promote_month` never reads it as an ARS
  deck. `ti/frame.py` is the slide frame chapters draw on; its `notes()` refuses a note with no
  Source line. `build_month` runs it only with `RPE_TI=1`; the launcher builds it on its own with
  `build <id> --ti` — CSM Sheila's **Transaction Intelligence** panel and button (Aaron, 2026-10-23:
  "a separate Transaction Intelligence presentation, separate from the currently approved RPE
  presentation"). `ars_launcher.ti_checks` is its readiness check: a chapter ported
  (`cut.CHAPTERS`), the client on ARS, this period's ODD extract, the client's codes
  (`ti/config`: the v5 config file, else `ars_code_tables.json`, parsed once per change), the
  transaction files for v5's window counted from file NAMES alone (`txn_stage` rules, no zip
  opened; Sheila keeps the folder listing for `SHARE_TTL`), and for the ICS lens the ICS lists
  (`lens.ics_list_files`). `ti_to_outputs` files the decks beside the RPE deck and supersedes
  only their own names; `decks_in_outputs` never counts a TI deck as the period's RPE deck and
  an RPE build never archives one (`is_ti_deck`). `tests/test_ti_launcher.py` pins all of it,
  so a change to any of those names is a change to the launcher too.
  Past five agenda rows (chapters + Questions) `build_ti_gen` keeps
  each chapter's heading and drops its detail line, which no longer fits. `ti/PORTING.md` holds the porting
  rules; `ti/compat.py` runs the ported code under v5's pandas 2 semantics inside a with-block, never
  process-wide (entry points and `test_ti_*` only); `ti/context.py` is the `Ctx` every computation
  is handed, shared by the build and the parity check; `ti/core/` the v5 foundation modules (periods, ODD transform, account bases, facts);
  `ti/odd.py` reads the client's ODD as v5 does; `ti/config.py` the client config the analyses
  read (a v5-shaped file when supplied, else derived from `ars_code_tables.json`, and said so);
  `ti/lens.py` the ARS and ICS lens groups, with the ICS lists found in `Inputs/ICS Direct Mail`
  and `Inputs/ICS Referrals` and joined onto the ODD by v5's `ti/monthly_analysis/ics_sources.py`;
  `ti/parity.py` + `scripts/ti_parity.py` check each ported analysis against a v5 run's own figures
  on v5's own frame (read-only; exit status = keys that differ).
  `ti_build.py` builds the cut for one client (figures once into `ti_pack.json`, a deck per lens);
  `build_month.build_client` runs it after the ARS deck only when `RPE_TI=1`, into `<stage>/<id>/ti/`,
  never delivered or combined. `docs/migration/DUPLICATES.md` records where the cut overlaps this repo.
  `ti/deck/` holds v5's chart renderers, headlines and copy rules (palette and face from `brand` /
  `use_font`) and `helpers.py`, the helper bundle v5's slide builders draw through, on RPE's anatomy.
  `ti/transaction_intelligence/` holds v5's transaction-file analyses; `ti/txn_stage.py` stages the
  window's zipped files from `Inputs/Txn Files/<id>/` once into a local cache for v5's loader;
  `ti/txn_sections.py` is v5's transaction run one section at a time, in v5's order;
  `ti/dictionaries/` the three reference dictionaries the transaction analyses classify against
  (competitors, financial-service patterns, merchant categories; copied from v5 `0_Config/`).
  `ti/chapters/` holds the cut's eight chapters in deck order (Transaction Intelligence, Competition,
  Attrition, Deposits, ICS accounts, Economics, Value, Campaign); `ti/chapters_txn.py` computes and
  builds the first two; `ti/deck/economics_inline.py`, `value_inline.py` and `campaign_inline.py` hold
  v5's economics, value and campaign slides, lifted out of v5's build function
  (`ti/deck/migration_slides.py` is v5's tier-matrix module); `tests/ti_v5_harness.py` stands in for v5's
  whole-month test harness; `ti/slides.json` sets every chapter and slide of the cut to "keep" or
  "toss" and `ti/selection.py` reads it (how the DUPLICATES overlaps get settled);
  `ti/odd_sections.py` runs v5's ODD sections; `ti/deposits_input.py` reads the client's own
  `Inputs/Deposits` file; `ti/workbook.py` is v5's ARS Workbook reader (`wb_*`: P&L, offers, Lift
  Matrix, rates) and `ti/workbook_input.py` finds the client's workbook by `build_month`'s rule and
  fills a blank `ICRate` / `NSF_OD_Fee` from it; `ti/guarantee.py` is v5's 2:1 deferral tracker reader
  (`gt_*`) and `ti/deferred_input.py` finds the client's tracker in `Inputs/Deferred Billing` and says
  when it is missing, stale or disagrees with the workbook.

*Standalone ARS tools — run by hand, not part of the deck chain:*
- `build_ars_onepager.py` — the 8.5x11 print one-pager. Deliberately skips
  restyle_fonts / fit_layout / validate_deck, which enforce the 13.33x7.5 deck contract.
- `responder_activity.py` — reads the raw ODD for the one-pager: eligible count, reach,
  depth, transactions over the ask. The before/after figures come from the shared
  `before_after.compute`, not from this file.
- `build_lift_matrix.py` — the Lift Matrix file for Bradford from the command line, without Sheila: a
  thin wrapper over `lift_values` (Aaron, 2026-09-25), same accounts, rates and file. `lift_extract.py`,
  its old `.pkl` step, is retired.

**`build/` (shared)**
- `restyle_fonts.py` — font-role post-processor, run last on every deck (all programs).
- `strip_dead.py` — zip-level dead-slide GC (called by the ARS assembler).
- `summit_slide.py` — inserts the Executive Summit slide (used by ICS/MRPC).
- `assemble_combined.py` — builds the combined ARS+ICS+MRPC deck from the three finished
  program decks (see **Combined decks** above).
- `fit_layout.py` — layout-fit pass + 10pt slide numbers; run by every builder before save.
- `cover_divider.py` — the cover and the section dividers, drawn the same way by all four
  builders (Aaron, 2026-10-02: "move the section dividers and title slides into main"):
  left-aligned navy, the client's logo, the month at 84 pt, product chips; a program divider
  carries its three headline figures and, in a combined deck, the progress track
  `assemble_combined.set_divider_tracks` draws. Keeps every invariant the pipeline reads off
  those slides (the "Executive Review  •  <month>" line, first text shape = title, the
  full-bleed rectangle, the 16 pt floor, no shadow). `tests/test_cover_divider.py` pins them.
- `slide_inventory.py` — every program's slide list from the templates and the builders, never from a client's deck (Aaron, 2026-10-29): the shell's titles with each builder's added slides spliced in at the builder's own anchor (`ADDED`), a shell slide the builder retitles (`RENAMED`), the Transaction Intelligence register and the Companion's view titles; the shell slides every deck shares are left out, a conditional slide carries its condition in `source`, and a lost anchor is stated. CSM Sheila's Slide Review reads it. `tests/test_slide_inventory.py`, and `tests/test_golden_deck.py` checks the ARS builder's own output against it.
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
`ics_local_sheet.py` (builds the ICS client sheet from local files — referral export, current workbook, Charts Goals tab, direct-mail list — when there is no VIP sheet; `build_month` uses it only then, 2026-09-16. **With the period's workbook and nothing else it builds the `workbook-only` shape** (Aaron, 2026-10-13, 1195 KEMBA CU): the ordinary referral block from the workbook's Monthly Detail row "Accounts Opened via Invitation Checking System" — **which counts referrals** (Aaron, the same day; it sums to the Value tab's figure) — and its DDA Openings by Branch tab, goals from the Charts Goals tab, names from it or the branch-name dataset, and notes that name the workbook row. The same three referral slides render it; for a few hours that day it was worded "accounts opened, not referrals", on the premise that the row was a different measure, and on 1776 the row runs above the referral detail export (2,575 vs 2,280), which is a question for the data team, not two measures. **The workbook's own ROI and Present Value are carried** (Aaron, 2026-10-13, "Carry the workbook's ROI figures"): `ics_workbook_extract` reads the Value tab's "Present Value of New ICS Accounts @ 3%" and "Present Value Per Account", and `build_ics_gen` shows them with the workbook ROI; the 2026-07-13 recalculation runs only for a sheet with no Present Value, the VIP pulls, and the notes say which was used), `ics_workbook_extract.py` (the quarterly step: populates a client JSON's workbook sections
from the ICS workbook — see **Cadence**; since 2026-10-13 also `monthly_detail_full`, every cohort
column of the Monthly Detail tab, which `build_ics_gen` renders as the **ICS appendix** — "Appendix:
Monthly Detail (k of n)", ten cohorts a page, after the education slides and before Questions &
Discussion so a combined deck keeps the pages in the ICS section; a sheet without the block gets no
appendix — and the Value tab's Present Value figures the deck carries with the workbook ROI. **Its `monthly_detail` block is the newest TWELVE cohorts** (nine until 2026-10-13) with the workbook's Total Expense row per cohort, and **its benchmark reads the Program to Date row** of Life of Account Data (Aaron, 2026-10-13, "Program-to-date everywhere"; `benchmark.window` says which row). **The revenue tiles on every ICS deck are program to date across every cohort** — `build_ics_gen` reads them from `revenue.components` / `revenue.total`, never from the cohort window, after Cindy's review of KEMBA found $11,044 "Interchange PTD" (nine cohorts) where the workbook's figure is $573,936; the chart subtitles name the window. The Financial Summary's expense lines are "Referral Fees to Date" (the workbook's Total Expense row) and "Acquisition Cost" ($245 × accounts, not deducted)), `data/` (per-client VIP ICS data — one folder per client; keep client-named).
**`build/mrpc_pipeline/`** — MRPC pipeline: `build_mrpc_gen.py`, `mrpc_charts_gen.py` (charts drawn at their slide slot size, `SLOT_IN`), `revenue_projection.py` (the projected year on Revenue by Year: a straight line through the last 6 complete months; Aaron, 2026-10-02), `mrpc_weekly.py` (the ONE reader of the MRPCEnrollmentSummary weekly, shared with the performance dashboard), `status_slides.py` (the Program to Date and Current Program Status slides, from that weekly; they replaced Card Portfolio and Key Metrics 2026-10-02), `setup_template.py` (one-time template bootstrap; needs `mrpc_template_base.pptx`, which is NOT in the repo — ask Aaron for it if the template must be rebuilt), `data/` (per-client VIP MRPC data).

**`templates/`** — ALL deck templates live here (consistent naming; passed to each builder as an arg).
- `ars_template.pptx`, `ics_template.pptx`, `mrpc_template.pptx` — the three stripped per-program shells the builders populate (cleaned + styled; "Union Financial" dummy client). **The only legitimate starting point for a build.**
- `multi-product_reference_deck.pptx` — combined ARS+ICS+MRPC reference (Union Financial demo, styled); source for re-materializing the stripped templates.
- `STYLE.md` — visual style guide (single source of truth). `TEMPLATES.md` — reference section map + template materialization.


**`prototype/`** — test-only deck experiments, never part of the pipeline or the gate:
`build_prototype.py` builds the redesigned Executive Review of
`docs/STYLE-PROPOSAL-2026-10-02.md` from a client's launcher data pack and VIP sheets into
the session scratchpad, so a change can be judged on real figures before any builder work.
The cover and dividers were moved into `build/cover_divider.py` from it (2026-10-02); the
rest is still a proposal.

**`validation/`** — `validate_deck.py` (pre-ship lint gate, 0 FAIL to ship), `qa_all.py`
(the full gate: every template + given decks, package integrity, layout drift), `layout_baseline.json` (the drift fingerprints — `--snapshot` to accept).
**`fonts/`** — Montserrat (headings) and Carlito (Calibri-metric, charts), both bundled and
embedded. `rpe_env.use_font` RAISES rather than let matplotlib substitute a missing face.

`archive/` and `dashboards/` are NOT in this repo — the initial import excluded them. They
live only in the pipeline data root. Nothing here references either.
