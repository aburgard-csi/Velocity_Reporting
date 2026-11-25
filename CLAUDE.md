# Retail Performance Engine — Deck Build Router

This project builds client Executive Review decks for four programs (ARS, ICS, MRPC, CashPlease), plus
the ILS, Transaction Intelligence and Summit work routed below. Each program has its own subagent and its
own data sources. **Keep them separate** — never run one program's logic while building another. Confusion
between programs is the exact problem this structure exists to prevent.

**Working here as a collaborator (not Aaron)?** Read `docs/COLLABORATORS.md` first: branches and pull requests, what not to run, and what to check before a PR.

This file holds the rules, tersely, each with its date and who said it. The reasons, the incidents and
the per-file detail are in the docs below (Aaron, 2026-11-25: keep the rules, move the history). **When a
rule changes, change it here and in the matching paragraph of its docs file.**

## Where the detail lives

| File | Read it when |
| --- | --- |
| `docs/FILE-MAP.md` | You touch a file you do not know, or add, move or remove one (update it in the same commit). The full per-file index. |
| `docs/PIPELINE-NOTES.md` | A rule below needs its reason, or you change the behaviour it describes: file locations and the full Inputs table, shared conventions, combined decks, ICS, the validation gate's history, complete months, the +/-2% band, cadence, Summit, data sources. |
| `docs/OPERATIONS-source-watch.md` | You edit `watch_sources.py`, `mail_sources.py`, the Drop Folder sweep, prune, the scheduled tasks or the watchdog. |
| `docs/OPERATIONS-dashboards.md` | You edit the delivery dashboard (`dashboard.py`, `deck_status.py`) or the RPE Client Performance artifact. |
| `templates/STYLE.md`, `templates/TEMPLATES.md` | Before building any deck (visual style, the single source of truth) / a shell's slide inventory and swap targets. |
| `docs/ILS-schema.md` | Before writing any ILS query. |
| `build/ars_pipeline/ti/PORTING.md` | Before any Transaction Intelligence work (with **Transaction Intelligence branches** in `docs/COLLABORATORS.md`). |
| `build/ils_pipeline/README.md` | ILS pre-go-live or kickoff work. |
| `CHANGELOG.md` | What changed and why; add an entry for every behaviour change (see **Repo rules**). |

## Routing

Identify the program from the request, then dispatch to the one matching subagent:

| Ask mentions… | Program | Subagent |
| --- | --- | --- |
| ARS, Account Revenue Solution, mailings, Lift Matrix, Reg E, debit take rate | ARS | `ars-deck` |
| ICS, Invitation Checking, referrals, mystery shop, ROI per account | ICS | `ics-deck` |
| MRPC, MyRewards Premium Cards, enrollments, Gold/Platinum tiers | MRPC | `mrpc-deck` |
| CashPlease, CP, small-dollar loans, loans per 1,000 DDAs | CashPlease | `cashplease-deck` |
| ILS analysis review, prep slides, matrix parameters / overrides | ILS prep (not an RPE build) | the `ils-prep-deck` skill for the prep slides; the ILS Program Analysis deck itself is built from the **ILS Review** card on a scheduled client's page in Sheila (`scripts/ils_review_runs.py`), which can also merge those prep slides in |
| ILS pre-go-live (PGL), ILS kickoff, a client's field summary or ILS codes | ILS pre-go-live / kickoff — James's v5 engines, run from the ILS cards on a client's page in Sheila | no subagent: `build/ils_pipeline/` (read its `README.md`); Sheila's cards are `scripts/ils_ui.py` and `scripts/ils_runs.py` |
| Transaction Intelligence, the TI cut, a lens (ARS lens / ICS lens), a chapter, the v5 port, parity, the duplicates register | Transaction Intelligence — a SEPARATE presentation, never an RPE build and never a change to one | no subagent: `build/ars_pipeline/ti/`, by hand, after reading `ti/PORTING.md` and **Transaction Intelligence branches** in `docs/COLLABORATORS.md` |
| An Executive Summit one-pager, a Summit handout, the Key Performance Metrics page, Summit attendees | Executive Summit one-pager: hand-built for ATTENDING clients only, never an RPE build and never scheduled | no subagent: the `summit-one-pager` skill (`.claude/skills/summit-one-pager/`), which also records Aaron's corrections to these pages |
| An HTML Artifact or web page for CSI / Velocity: a guide, catalog, dashboard, report or comparison, or the Design Library | A shared page, not a deck | no subagent: the `velocity-artifact-design` skill (`.claude/skills/velocity-artifact-design/`), on top of the bundled `artifact-design` |
| Rebuild a set of clients' decks for a period (after a fix, a CSM's book) | Launcher builds, one at a time | the `rebuild-decks` skill |
| A deck that fails the validation gate | Fix the builder, then rebuild | the `fix-deck-failure` skill |
| Did the morning tasks run, the scheduled tasks or the tasks checkout | A read-only health check | the `tasks-health` skill |
| A new or changed CSM Sheila tab, card or button | Sheila's page and routes | the `sheila-change` skill |
| Refresh or republish the RPE Client Performance dashboard | Hand run of the 08:30 refresh | the `publish-dashboard` skill |

If a request names a client but not a program, ask which program before building. If it
asks for a combined ARS+ICS+MRPC review, run each subagent in turn and assemble with
`build/assemble_combined.py` (see **Combined decks**) — do not improvise one blended path,
and do not start from an existing combined deck.

**`clients.md` decides which clients get which programs** — never infer membership from an input file on
disk (a cancelled client's leftover data kept producing a section). Check it before building; update it
when a program starts or stops (the `add-client-to-roster` skill).

## File locations

Detail: `docs/PIPELINE-NOTES.md`, File locations (the full Inputs table, VIP Data, logos, archive history).

- **Every path resolves from `RPE_DATA_ROOT`** (`build/rpe_env.py` → `inputs()` / `outputs()`), set per
  machine in `.env`. **Do not hardcode a path anywhere** and do not reintroduce a per-machine branch in the
  build code; if the root moves, repoint `RPE_DATA_ROOT` in `.env` and nothing else. If a build's inputs
  aren't where `RPE_DATA_ROOT` says, ask Aaron to point at the specific file rather than guessing, but do
  not re-ask the whole walk-through each session.
- **The root is `\\PADMIS105\Velocity_company\CSM_Reporting\`, the ONE copy (Aaron, 2026-09-14)**; it needs
  the VPN off-site. The old local root `C:\Data Pipelines\RPE Pipeline (retired 2026-09-14 - use CSM_Reporting)\`
  is retired: do not point anything back at it. `C:\Data Pipelines\Renewals Pipeline` is a DIFFERENT
  project: nothing here ever reads or writes it.
- **No mirror and no second copy (Aaron, 2026-09-09).** The original sources are the backup
  (`scripts/watch_sources.py --copy --mail` re-fetches them); two stores for one fact is how month-old ICS
  figures shipped and validated.
- **Inputs are filed in a folder per KIND (Aaron, 2026-09-09).** The names live in `rpe_env.INPUT_KIND_DIRS`
  and nowhere else; readers glob `rpe_env.report_dirs()` / `report_files()`, never a literal folder.
- **Write hazard on mounted folders.** Some mounts allow creating and copying files but NOT
  deleting. If a file must be replaced or removed, ask Aaron. Confirm the writable target per session.

The main folders under `RPE_DATA_ROOT` (the full table, with each kind's naming and reader, is in
`docs/PIPELINE-NOTES.md`):

| Input | Folder |
| --- | --- |
| ODD extracts `<id>_ODDD.zip`, no period in the name | `Inputs/ODDD/` |
| DCOs; ARS workbooks | `Inputs/DCOs/`; `Inputs/ARS Workbooks/` |
| MRPCPM analyses and the MRPCEnrollmentSummary weeklies | `Inputs/MRPC Analyses/` |
| ICS workbooks; ICS Charts (mystery shops); referral exports; direct-mail lists | `Inputs/ICS Workbooks/`; `Inputs/ICS Charts/`; `Inputs/ICS Referrals/`; `Inputs/ICS Direct Mail/` |
| CashPleaseSummary weeklies and `ILS-DDA-Count-<date>.txt`; marketing emails; production settings | `Inputs/CashPlease/`; `Inputs/CashPlease Marketing/`; `Inputs/Product Settings/` |
| ARS code tables (never the export's settings table: it holds plaintext credentials); client code sheets | `Inputs/ARS Settings/`; `Inputs/Code Sheets/` |
| ICS / MRPC client sheets from VIP (the ONLY source: `rpe_env.resolve_client_json(id, program)`) | `Inputs/VIP Data/<PROGRAM>/<id>-<Name>/` |
| Debit-card transaction files, stored zipped, read only through `rpe_env.txn_files()` / `open_txn()` | `Inputs/Txn Files/<id>/` |
| ILS: deposits; analysis pulls; pre-go-live; kickoff; finished reviews | `Inputs/Deposits/`, `Inputs/ILS Analysis/`, `Inputs/ILS PGL/<id>/`, `Inputs/ILS Kickoff/<id>/`, `Inputs/ILS Reviews/<id>/` |
| REMS responses; GL data; branch names; market reference; logos | `Inputs/REMS/`, `Inputs/GL Data/`, `Inputs/Branch Names/`, `Inputs/Market Reference/`, `Inputs/Logos/` |
| Anything unrecognised (read, never written) | `Inputs/ARS & MRPC Reports/` |
| Files a person drops by hand (swept by the 08:00 file get) | `-Drop Folder/` at the root |
| Build evidence, launcher working files (NOT deliverables) | `Build Artifacts/`, `Build Artifacts/launcher/<period>/<id>/` |
| The peer reference | `Peer Reference/` |
| Template shells | the repo's `templates/` |

**Nothing client-identifiable belongs in git**: logos (`Inputs/Logos/`, read through `rpe_env.client_logo`,
`trim_logo`, `fit_box`; a missing logo never fails a build), customer lists, query results, client data.

**`Outputs/` holds finished decks and nothing else (Aaron, 2026-08-29).** Anything a build emits to prove
itself goes to `Build Artifacts/` (`rpe_env.build_artifacts()`). One exception: a Transaction Intelligence
build's mail lists go out as `Outputs/<CSM>/<id>-<period>-TI-Lists/` (Aaron, 2026-11-23), archived like a deck.

**Output — ONE destination (Aaron, 2026-07-25), filed by CSM (Aaron, 2026-09-14).** Every finished deck goes
to `Outputs/<CSM>/`, resolved by `rpe_env.client_outputs(id)` (`Client CSM List.csv`, else the CashPlease
roster's CSM column, else `Outputs/_Unassigned/` — never a guessed CSM); readers use
`rpe_env.output_decks(pattern)`. Program is distinguished by the filename tag, not by subfolder. Do not
deliver to client folders and make no per-client Delivery copies. Superseded decks go to the CSM's own
`Outputs/<CSM>/_Archive/<id> <client>/` (Aaron, 2026-10-15); `promote_month` moves older ones to
`_older decks - delete after review/`, never deletes them and never moves a hand-made PDF.

## Shared conventions (all programs)

Detail: `docs/PIPELINE-NOTES.md`, Shared conventions (the incidents behind each rule).

**Decks ship as `.pptx` only — do not generate a PDF** (Aaron, 2026-07-24): no LibreOffice/`soffice` step,
no `.pdf` alongside the deck.

**Filename convention:**

```
<clientid>-<yyyy.mm>-<PROGRAM>-<Client Name> <PROGRAM> Results.pptx
```

- `<PROGRAM>` is one of `ARS`, `ICS`, `MRPC`, `CP`, or the included tags joined in
  section order for a combined deck (`ARS-ICS-MRPC`, `ICS-CP`, `ARS-ICS-MRPC-CP`).
- `<yyyy.mm>` is the data/period month, e.g. `2026.07`.
- `TI` and `COMP` (Transaction Intelligence, ARS Companion) are not program tags: those decks are filed
  beside the RPE deck, never counted as the period's RPE deck and never archived by an RPE build.

**Combined decks — the standard for multi-product clients (Aaron, 2026-08-27).** A client on more than one
program gets ONE combined Executive Review. Build each program's deck first (each must pass its own
validation gate), then assemble:

```
python3 build/assemble_combined.py [--ars <ars.pptx>] [--ics <ics.pptx>] [--mrpc <mrpc.pptx>] \
                                   [--cashplease <cp.pptx>] --out <out.pptx>
```

- Any two or more programs make a combined deck; `--ars` is not required (Aaron, 2026-09-01): the first
  program in `BASE_PRECEDENCE` (ARS, ICS, CP, MRPC) supplies the shell and Questions/Contact. The ARS
  Appendix exists only with an ARS section.
- The title slide lists only the included products; an unused agenda row is REMOVED, not blanked. Each
  program deck's own title / Summit / agenda / Q&A / Contact slides are dropped so there is one of each.
- The assembler only ADDS slides and reorders them: a freed slide part name is handed to a later slide and
  the package references parts twice (the unopenable-deck defect). Run `validation/qa_all.py` on the result.

**The ICS section presents current results only (Aaron, 2026-08-28).** Workbook-driven ICS elements ship only
when the newest ICS workbook (via `rpe_env.report_dirs()`) is for the deck's own period; otherwise the
section falls back to the referrals-only shape (Referrals, Referral Trend, Results by Branch, the education
slides; divider "Referrals"). Do not carry an older workbook's figures forward, and do not re-date, align or
zero them; an ICS section older than its neighbours is a defect. A client live before its first workbook
builds with the opt-in `build_ics_gen.py --referrals-only` (Aaron, 2026-08-27); without the flag the
missing-section guard stops the build. The ICS revenue tiles are program to date across every cohort, never
the cohort window (Aaron, 2026-10-13). Direct-mail accounts get their own slide and are never added to
referral counts.

**Contact Us = the managing CSM (Aaron, 2026-09-16).** Every Contact card is the client's CSM with their row in
`<RPE_DATA_ROOT>/CSM Contacts.csv` (`rpe_env.csm_contact`). Never hardcode a person's card. No CSM or no
contacts row stops the build — add the row, never fall back to another CSM. Standalone ICS decks add the ICS
program contact (`rpe_env.ICS_PROGRAM_CONTACT`) as a second card.

**Templates — build from the shell, never from a client deck (Aaron, 2026-08-29).** Each builder populates the
stripped shell in `templates/` (`ars_template.pptx`, `ics_template.pptx`, `mrpc_template.pptx`,
`cashplease_template.pptx`; "Union Financial" dummy client). **No deck is ever cloned from another client's
finished deck** (that is how a reference client's numbers, captions and notes leaked). If a slide is wrong,
fix the BUILDER and the template shell, then rebuild. Do not hand-edit a deck and do not reach for a
previous client's file as a starting point. `multi-product_reference_deck.pptx` is a STYLING reference, not
a build input.

**Resolve slides by TITLE, never by index.** **Swap gate (2026-07-25): a text swap that matches nothing FAILS
the build** — a silent no-op ships the template's numbers. **The closing slide carries the cover's client
and month (2026-09-17)**; `validate_deck.closing_month_findings` FAILs a mismatch.

**A slide with no data is left out, and said so — never zeroed (Aaron, 2026-11-22: "skip a slide if it
doesn't have data").** This replaced "missing source data is stated" and "never drop slides automatically".
- No 0%, empty chart or stand-in figure is ever drawn; the slide is not in the deck.
- Never silent: the build log prints `slide left out (no data): <title> - <why>`.
- A slide is only taken out with `shapes.drop_slide` (or never put in the deck's order and removed by
  `strip_dead`), never by freeing a part name another way.
- Absent data is a data-sourcing question first: if it is carried in another source (Reg E in the workbook
  rather than the ODD), populate the slide from there. A tile or caption on a slide that does carry data
  still states its gap ("n/a"). A failure to READ data is a build failure, never quietly skipped.

Transaction Intelligence exception (James Gilmore, 2026-10-30): a TI slide whose builder declines for a
client is hidden from that client's deck, and a chapter with every slide declined loses its divider and
agenda row; each one is logged and listed in `hidden_declined.json` (`build_ti_gen.build`).

**Data sources in slide notes — always (hard requirement).** Every slide lists its data source(s) in its
speaker notes: the source file or dashboard (ODD extract + pull date, workbook tab, VIP dashboard, ICS
Charts, MRPCPM Analysis, …) and the selection/period behind the numbers. No slide ships without a source line.
The notes name **the client being built** — its id, name, ODD pull stamp and workbook filename — derived from
the data pack, never hardcoded and never the reference/template client. **Verify every build:** grep the
finished deck's notes for the reference client (e.g. "CoastLife", "1705") — zero hits required — and confirm
the client id, pull stamp, workbook name and MM-vs-SM tab wording.

**Standardized category values (every build, every client).** Normalize to one fixed vocabulary — never
invent a mapping:

- **Reg E opt-in status** → `Reg E Opt In`, `Reg E Opt Out`, `Reg E Default`.
- **Account status** → `Open`, `Closed`, `Dormant`, `Inactive`, `Frozen`, `Charged Off`, `Other`.
  Core lifecycle wording confirmed by Aaron (2026-07-25): `Purge at Yearend` and `Pending Closeout` →
  **Closed**, `New This Cycle` and `Pending Activation` → **Open**, `Manually controlled` → **Other**.
- **Status CODE fallback** (Aaron, 2026-08-28), used only when `Stat Desc` is blank:
  `oddd_optimize.STAT_CODE_MAP`, **`O`/`A` → Open, `C` → Closed, `X` → Charged Off**.

`oddd_optimize.py` applies these (`classify_rege` / `classify_status`). Blank Reg E cells are excluded; a
blank status with no usable code falls to `Other`. Any non-blank value that doesn't map is surfaced in the
pack's `flags` block — **ask Aaron how to map it before building; do not guess.** An unmapped code is
corrected on the client's code sheet by the CSM, never forced in code.

**Visual style guide.** Every client-facing deck follows `templates/STYLE.md` (palette and type roles from
`build/brand.py`, the ONE source). **Read it before building any deck, and keep it as the single source of
truth for visual style.**

**Writing style.** All client-facing text follows Aaron's writing rules, recorded
here in full rather than pointed at elsewhere. Banned words include: robust, comprehensive,
leverage, seamless, delve, and the banker-deck list — engine, lever, lift (as prose;
"ARS Lift Matrix" as a proper slide name is fine), ramping, healthy, predominantly,
companion, seasoned book, annuity. No superlatives or unsupported higher/lower claims.

**Comparisons use complete months only (Aaron, 2026-09-17).** "Don't calculate YoY or
comparisons on partial months, only use complete months."
- `build/month_complete.py` is the one definition, per MEASURE: a month is incomplete when the data was
  pulled before it ended, or its total is below half the median of the six months before it. A month that
  collapses in the MIDDLE of an extract is left out too (2026-10-13): read `usable_months(months, result)`,
  never `months[:complete]`.
- Every YoY, month-over-month, latest-month tile, trend endpoint and trailing window uses the last complete
  month of the measures it reads. Do not write a new "latest month" read of an activity series without going
  through it. Status snapshots (Elig, Reg E, account status) still read the snapshot month.
- A left-out month is STATED on the slide and with its figures in the notes — never zeroed, never charted
  as a collapse, and its slide is never dropped.
- YoY tiles are year to date against the prior year to date (Aaron, 2026-10-12); every month of both windows
  complete, else n/a. Where the series does not reach back to January of the prior year, spend falls back to
  like for like over at least three months (Aaron, 2026-10-15).

**Describing movement — the +/-2% band (Aaron, 2026-08-31).** A sentence that says a
measure moved must agree with the figures beside it:

| Change | Say |
| --- | --- |
| within **+/-2%** | "almost flat" |
| **positive** | state the increase — the figures and the % |
| **negative** | say it did not have an impact on that measure |

The verb is DERIVED, never written as a constant. **A claim with no figure behind it is not checkable**:
state the figures, or do not make the claim. `validate_deck.claim_consistency_findings` FAILs a mismatch.

**Peer comparisons.** `build/peer_compare.py` is the ONE arithmetic (decks, Live Review, Sheila in Claude).
- Peers are anonymous: a peer is a client NUMBER at most — never a name, logo or CSM (Aaron, 2026-11-03).
  Fewer than five peers is stated, not shown.
- Never more than two comparisons on a slide (Aaron, 2026-11-22).
- ARS is compared only on what the client controls (`peer_pool.ARS_METRICS`: Reg E, take rate, account
  growth, retention), never on program results (Aaron, 2026-11-22).
- A client-facing CashPlease peer figure is the MEDIAN of the other current clients; the pooled book is
  internal only (Aaron, 2026-11-24).
- `validate_deck.peer_slide_findings` fails a peer slide that could not read its peers or names another client.
- `Peer Reference/` (every peer figure, tagged and dated; Aaron, 2026-11-20) is refreshed by a detached
  process after each deck build (2026-11-22); a build never waits on it or depends on it.

**ARS rules that live in the builders.** A ratio is printed only by `revenue_guarantee_slide.ratio_text`,
from the unrounded quotient (2026-10-12). A workbook with unevaluated formulas is stopped by `base_guard.py`
(`UNEVALUATED WORKBOOK`: open it in Excel, save, rebuild). An MM client's build stops when the data month is
past the Lift Matrix End Date or the workbook name carries the data team's flag (`ars_launcher.lift_checks`).
The Lift Matrix file exported for Bradford is never written to Outputs.
The James / Companion / spend views are opt-in (`RPE_JAMES_SLIDES`, `RPE_SPEND_SLIDES`, `RPE_TEST_SLIDES`);
the ARS Companion and Transaction Intelligence are SEPARATE decks that never change the approved Executive
Review, its metrics or its template.

## Validation and the QA gate

Detail: `docs/PIPELINE-NOTES.md`, Validation gate and QA gate.

**Validation gate.** Run `validation/validate_deck.py <deck> [base.json]` on every built
deck before it ships. A non-zero exit blocks delivery — fix and re-run, do not override.

**QA gate — run after ANY change to `templates/`, `build/`, or `validation/` (2026-07-24):**

```
python3 validation/qa_all.py [built_deck.pptx ...]        # gate: validates every template + given decks
python3 validation/qa_all.py --snapshot ...               # accept INTENTIONAL layout changes as the new baseline
python3 validation/qa_all.py --no-tests ...               # skip the unit suite (know why)
```

- Run it from the repo `.venv` (`.venv/Scripts/python` on Windows); the Windows Store `python` has no pytest.
  The unit suite (`pytest tests/`) is its step 0; skip it with `--no-tests` only when you know why.
- **DRIFT warnings mean a shared pass touched slides you didn't intend to change.** Review them, then
  `--snapshot` to accept.
- **Standing rule (Aaron, 2026-08-17): when a defect gets through the gate, add the check
  that would have caught it.** Fixing only the instance guarantees the next one ships too.
- The LibreOffice render test was removed on 2026-09-11 (no renderer on the build machine). Do not add it
  back without the renderer to run it. Nothing in the gate now proves a deck renders; the package check
  (`validate_deck.package_findings`) covers structure only. **Open one deck before a batch goes to clients.**

Three hard-won rules (cited by number in the code):
1. **Nominal font size is not rendered font size.** `normAutofit` silently shrinks text; the validator FAILs
   any frame with fontScale <90%. Never trust nominal font sizes on template-inherited frames.
2. **Box geometry is not glyph geometry.** Fix layout in the BUILDER/geometry contract (`slide_geometry.py`,
   `fit_layout.py`, `textfit.py` — never eyeball whether a label fits) — never hand-edit one deck.
3. **python-pptx is not the file.** It enumerates a duplicated slide reference as two slides;
   `package_findings` reads the ZIP directly and is the only check that sees that class of defect.

## Shared layer and build machinery

Detail: `docs/PIPELINE-NOTES.md`, Build machinery and Shared layer; `docs/FILE-MAP.md`.

- Code that is not specific to one program lives in `build/` root and serves every program: `brand.py`,
  `shapes.py`, `periods.py` (every derived date phrase; never hand-derive a span or a count),
  `month_complete.py`, `slide_geometry.py`, `fit_layout.py`, `restyle_fonts.py`, `table_style.py`,
  `cover_divider.py`, `textfit.py`, `summit_slide.py`, `assemble_combined.py`, `rpe_env.py`. A change there
  can alter every program's decks at once.
- `metrics_gen` reads `sys.argv` at module scope, so importing it RUNS it; `odd_rows.py` and
  `before_after.py` are import-safe on purpose — never re-implement them standalone.
- `rpe_env.use_font()` RAISES rather than let matplotlib substitute a missing face; every chart renderer
  goes through it.
- `build/assets/summit_slide.pptx` is the ONE Summit slide (Aaron, 2026-09-11); replace it there (or at
  `Inputs/Summit/summit_slide.pptx`) and rebuild.
- Retired code (the pre-`build_ars_gen` recipe, `*_orig` backups, the old combined-Marine helpers) is not in
  this repo, and nothing should import it.

## Cadence

Detail: `docs/PIPELINE-NOTES.md`, Cadence and Executive Summit one-pagers.

ARS, ICS and MRPC deliver **monthly**; **CashPlease is weekly**. Nothing is quarterly: the quarterly ICS
workbook gates which SECTIONS carry current figures, never whether the deck ships.

| Program | When | Scope |
| --- | --- | --- |
| ARS | Monthly | Every ARS client, each month — MM or SM path per client |
| MRPC | Monthly | Every MRPC client, each month |
| ICS | Monthly (Aaron, 2026-08-31) | Referrals monthly; financial detail only with the deck's own period's workbook (see **The ICS section presents current results only**) |
| CashPlease | **Weekly** | The build **always uses the most recent** CashPleaseSummary weekly (Aaron, 2026-09-01), so a CP section can carry a later date than its neighbours: its pill keeps its own `PTD · <date>` and is never re-dated. Scope is the `### CashPlease roster` table in `clients.md` — never the workbook, which carries every client of every CSM. |

### Executive Summit one-pagers — NOT a canned deliverable

**The Summit one-pagers are hand-built, per attendee, and are never generated on a schedule
(Aaron, 2026-08-31).** They go only to clients who are ATTENDING; which metrics they show is Aaron's
judgement. Build them through the `summit-one-pager` skill and record his corrections there (2026-10-30).

- **Do not add the one-pager to the monthly run.** `scripts/build_month.py` must not learn to emit one-pagers.
- **Do not build one for a client who is not attending**, and do not build the full roster
  "so they are ready". Ask Aaron which attendees need one.
- **Do not pick the metrics.** Ask rather than choosing what looks best.
- Never derive a monthly deck's reporting month from the Summit date. The Summit slide in every monthly
  deck is a standing branding slide, unrelated to who attends.

## Delivery dashboard

Detail: `docs/OPERATIONS-dashboards.md`; the source watch in `docs/OPERATIONS-source-watch.md`.

**Delivery dashboard:** `python3 scripts/dashboard.py [--period 2026.09] [--port 8787] [--no-source]`, loopback
only (it has a write endpoint); `scripts/deck_status.py <period> --json out.json` gives the same document.
- **Sent is recorded, never inferred**: written to `Build Artifacts/deliveries.json` by the Mark sent button
  (Aaron, 2026-08-31). A deck in Outputs proves only that it was built. A damaged log raises.
- **The CSI shares need the VPN (Aaron, 2026-08-31).** Off VPN a share is *unknown*, never empty.
- **An ODD extract in `Inputs/` is only current if the SOURCE says so** (the share, the watch's landing
  record, or the extract's own pull stamp). Stale blocks exactly as hard as missing.
- ICS workbooks arrive by email; a missing one does not block (the section builds referrals-only).
- Share paths come from `RPE_SRC_ODDD` / `RPE_SRC_REPORTS` and friends, never hardcoded.

### Daily source watch

```
python scripts/watch_sources.py [--notify] [--dry-run] [--period 2026.09 ...]
python scripts/watch_sources.py --check-stale     # has the daily watch been running?
powershell -ExecutionPolicy Bypass -File scripts\register_watch_task.ps1 \
        [-Time 08:00] [-Repo <checkout>] [-RetryHours 0] [-Unregister]
```

- **The file-get runs ONCE a day, at 08:00, and no more (Aaron, 2026-10-05).** Do not start a hand-run beside
  it. The one sanctioned second fire is the watchdog's retry on a morning the 08:00 fire never executed.
- The task "RPE Source Watch" runs as the logged-on user with a 50-minute limit. `-Repo` targets a
  checkout other than the script's own: the scheduled tasks run from their own checkout
  (`RPE_TASKS_CHECKOUT`), which each release moves to the commit it released (Aaron, 2026-11-24).
- **Off VPN it exits 2 and leaves the saved inventory alone.**
- **Health is checked from OUTSIDE the watch** — do not "simplify" this by having it check its own health.
  The "RPE Source Watch Watchdog" fires once at 08:10 (Aaron, 2026-10-15); a later check is a hand run. A
  `watch_sources.py` process older than 3 h is stuck whatever its counters say (Aaron, 2026-10-07).
- **Copy:** copy-only, never deletes; every client except a stopped one; the ODD extract only from the newest
  month on the share; a "differs" file is overwritten only when the SOURCE is the newer write; small files
  first; one unreachable CSM folder counts as off VPN.
- **Drop Folder (Aaron, 2026-11-16):** swept by the same `--copy`. A different file of the same name in
  `Inputs/` is never overwritten, except an ODD extract whose own pull stamp is newer, which replaces the held
  one (archived to `Inputs/ODDD/_Archive/`, never deleted) (Aaron, 2026-11-22).
- **Prune:** deletes a file only when a newer non-empty version of the same client and kind is present;
  never ODD extracts or ICS Charts workbooks.
- **Mail:** Outlook read-only (nothing marked read, moved, deleted or replied to); it cannot hang the run.
  The child writes to FILES and a timeout kills its process tree: **do not hand a child `subprocess.PIPE`
  with a timeout anywhere here.** Each sender may supply only their own kinds; an attachment whose name
  does not match is parked and reported, never guessed at.
- `--issues` runs here because `gh` is authenticated on this machine only. `--ils-analysis` lists, never
  copies; `land_ils_analysis.py --apply` is its own 08:20 task, registered by Aaron (never run for him).
  Transaction files are landed by hand (`land_txn_files.py`), never by the watch.

### The performance dashboard artifact

```
python scripts/refresh_performance_dashboard.py [--period 2026.08] [--csm "Aaron Burgard"] [--force]
python scripts/refresh_performance_dashboard.py --mark-published
```

- The "RPE Client Performance" artifact is `https://claude.ai/artifact/F4jLMLqxmQdBNYXpJHH6We`. **Do not
  create a new artifact for this page** — republish to the URL, or the link people hold goes stale.
- The script never publishes. The Claude scheduled task `rpe-dashboard-refresh` (daily 08:30) republishes
  only on `STATUS: changed`, then runs `--mark-published`.
- The period is the calendar month (Aaron, 2026-10-02); each client shows its own newest figures within it.
- **The page lists ONE CSM's clients (Aaron, 2026-11-02)**; there is no all-CSMs option. CashPlease company
  rows are medians, counts, rates and averages only, never a client's volume (Aaron, 2026-11-24).
- Edit `scripts/perf_dashboard_template.html` and `scripts/perf_workflow.html`, never the published copy.

## Data sources by program (do not cross these)

Detail: `docs/PIPELINE-NOTES.md`, Data sources by program (each source's folder).

- **ARS** — raw ODD via the `oddd-optimizer` subagent (run it first), plus the ARS
  workbook (Lift Matrix MM tab / `base_extract.json`) and DCO. ODD-driven.
- **ICS** — ICS Workbook (ROI, lifetime value, revenue, financial summary), VIP ICS
  Referral dashboard (referral counts/trend/branch), ICS Charts 2026 (mystery shops).
  Not ODD-driven; `oddd-optimizer` is not used.
- **MRPC** — VIP MyRewards Premium Cards dashboards + the MRPC workbook (MRPCPM Analysis) and the
  MRPCEnrollmentSummary weekly. Not ODD-driven.
- **CashPlease** — the newest CashPleaseSummary weekly and the weekly DDA count (`Inputs/CashPlease/`),
  the production settings (`Inputs/Product Settings/`) and the marketing emails
  (`Inputs/CashPlease Marketing/`). Not ODD-driven.
- Every input is read from its `Inputs/` kind folder (see **File locations**); if a file is not where it
  should be, ask Aaron to point at it rather than guessing.

## Sheila, the launcher and releases

Detail: `docs/FILE-MAP.md` (`ars_launcher.py`, `ars_launcher_web.py`, `sheila_hub*.py`, `sheila_mcp/`, `release_launcher.ps1`).

- `scripts/ars_launcher.py` builds one client's deck and puts a 0-FAIL deck straight into
  `Outputs/<CSM>/`, archiving what it supersedes. No staging step: each CSM reviews, PDFs and emails the
  deck from Outputs (Aaron, 2026-09-15). `build <id> --ti` / `--companion` build the separate decks.
- `scripts/build_month.py` builds a period's monthly reviews from the `clients.md` roster into a staging
  folder; `promote_month.py --apply` delivers. It never emits Summit one-pagers; TI only with `RPE_TI=1`.
- **CSM Sheila** (`scripts/ars_launcher_web.py`, the page in `scripts/sheila_hub*.py`) serves on 127.0.0.1
  only with a token; builds run one at a time per PC (`%LOCALAPPDATA%\RPE\build.lock`); it decides nothing
  itself. Her issue button QUEUES and never calls GitHub. **Sheila in Claude** (`sheila_mcp/`) is delivered as
  a Claude Desktop extension, never through the launcher (James Gilmore, 2026-10-30): `runtime.cmd` and the
  launcher .bat files never touch Claude. It replaces a deck in Outputs only after the CSM's yes. In Sheila,
  Aaron's multi-program clients get only the combined build. Slide Review votes are per program template,
  never per client, and a program's slide list is read from the build, never from a deck.
- **Live Review** (`scripts/live_review.py`, `build/review_page/`) is run by hand or from Sheila; it is never
  in Outputs or `deliveries.json`, and its traceability audit is a hard refusal.
- **The launcher runs the released copy: re-run `release_launcher.ps1` after any change, `clients.md`
  included. A release ships origin/main and nothing else (Aaron, 2026-10-07).** Nothing merges or releases
  without Aaron's word (the `merge-and-release` skill). Bump `VERSION` by hand in the commit that adds a
  major feature.
- **RPE Decks and ILS Decks** (Aaron, 2026-11-25): Sheila's sidebar lists RPE clients (any RPE program) under RPE
  Decks and every ILS client (review schedule, landed pre-go-live / kickoff inputs, the clients.md ILS roster)
  under ILS Decks; a client on both is on both. A client page opened from ILS Decks shows ILS only, from RPE
  Decks RPE only. Detail: `docs/FILE-MAP.md`, `sheila_hub.py`.
- The team issue pages (`scripts/issue_pages/`) are not published now: do not republish them unless Aaron
  asks.

## Repo rules

Detail: `docs/FILE-MAP.md`, Root and `.github/`; `docs/COLLABORATORS.md`.

- **`CHANGELOG.md` records every correction and change (Aaron, 2026-09-01)**: a moved number or source, a
  changed claim, AND a change to what a slide renders. Post to it whenever you change pipeline behaviour.
  **Every entry starts with a `Summary:` line** — one or two plain sentences for a CSM (2026-09-25).
- **ILS databases:** Claude cannot reach them (nor VIP or MRDB). Read `docs/ILS-schema.md` before writing any
  ILS query; SQL in `sql/` is run by a person. Customer lists and results never go in the repo.
- **`.github/`:** CI runs the unit suite on every PR and push to `main` against an empty `RPE_DATA_ROOT`;
  `CODEOWNERS` requests Aaron's review for `build/`, `validation/`, `templates/`, `clients.md`, `CLAUDE.md`,
  `.github/` and the release and task scripts.

## Project map (short — the full index is `docs/FILE-MAP.md`; keep it current there)

| Folder | What is in it |
| --- | --- |
| `build/` | The shared layer (above) and the pipelines: `ars_pipeline/` (`build_ars_gen.py`, `metrics_gen.py`, `companion_deck.py`, `ti/` + `build_ti_gen.py`), `ics_pipeline/` (`build_ics_gen.py`), `mrpc_pipeline/` (`build_mrpc_gen.py`), `cashplease_pipeline/` (`build_cp_gen.py`), `ils_pipeline/`, `ils_analysis/`, `review_page/` (Live Review). |
| `scripts/` | Entry points: `build_month.py`, `promote_month.py`, `ars_launcher.py`, `ars_launcher_web.py` + `sheila_hub*.py` (Sheila), `build_cashplease.py`, `oddd_optimize.py`, `watch_sources.py`, `deck_status.py`, `dashboard.py`, `refresh_performance_dashboard.py`, `release_launcher.ps1`, `live_review.py`, `register_*.ps1`, `launchers/`. |
| `sheila_mcp/` | Sheila in Claude (the Claude Desktop extension's server). |
| `validation/` | `validate_deck.py` (0 FAIL to ship), `qa_all.py` (the full gate), `layout_baseline.json`. |
| `templates/` | The per-program shells, the reference deck, `STYLE.md`, `TEMPLATES.md`. |
| `tests/` | The unit suite (synthetic data only). |
| `docs/`, `sql/` | The docs above, PRDs; ILS queries a person runs. |
| `.claude/` | The deck subagents and the skills named in **Routing**. |
| `fonts/` | Montserrat and Carlito, bundled and embedded. |
| `prototype/` | Deck experiments, never part of the pipeline or the gate. |
