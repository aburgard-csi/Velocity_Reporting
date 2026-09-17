# Changelog

Behavior changes to the deck pipelines. The point of this file is that a
reversal like the 2026-08-20 one below should be findable without reading an
80KB source file.

Record corrections and changes (Aaron, 2026-09-01): anything that changes a
number on a client-facing slide, changes where a number is sourced from, changes
what a slide claims, or changes what a slide RENDERS. A fix that moves no figure
still belongs here — the MRPC retention line below moved no figure and could not
be seen on any deck that carried it. Judging an entry by whether a number moved
is how a correction goes unrecorded.

Format: newest first, dated, with the reason — not just the change.

---

## Unreleased

### 2026-09-17 — CashPlease settings for 68 clients; prepaid finance no longer reads "N/A%"; September pill fits

Settings records: `Inputs/Product Settings/` went from one file (1632) to 68, exported from an
all-clients pull of the Business Utilities CashPlease records (`C:\Data Pipelines\Product
Settings\Inputs\CashPlease`, Aaron: "copy it to Sheila's inputs folder"). Test accounts and the 18
clients with no loan settings recorded get no file, so they keep getting no settings slide.

Three rendering defects that the wider data exposed on the first 2026.09 modules (Aaron: "build
the CashPlease modules for my clients"), all in `build_cp_gen.py`:
- **Prepaid finance charge** appended "%" to anything not ending in one, so slides read "N/A%
  (standard & MLA)" (1750, 1771), "6% / $25 max%" (1131), "6% up to $25 MAX%" (1770) and "$20%
  standard · $0% MLA" (1564). `_as_pct` now signs a bare number only, and the new `_as_charge`
  shows N/A/0 as "None" (a lone "None" drops the "(standard & MLA)" tail).
- **Four differing loan types** were lower-cased ("22% easy std · 23% manual mla"); they now keep
  "Easy Std / Manual MLA".
- **The content-slide date pill** is 2.70" wide (was the 2.35" `shapes.pill` default): "PTD ·
  September 13, 2026" is 2.16" of Montserrat 12pt in 2.15" usable and wrapped onto two lines on
  every content slide. It grows leftward into the gap after the title.
Tests: `test_cp_settings_slide.py` pins all three. Rebuilt 1131, 1564, 1750, 1770, 1771 — 0 FAIL,
0 REVIEW. Re-assembled the combined decks 1539 (ARS-ICS-MRPC-CP, 72 -> 73 slides), 1632 and 1734
(ICS-CP, 1734 19 -> 20) from the same ARS/ICS/MRPC decks they shipped with and a fresh CP section
(`Build Artifacts/cp_settings_2026.09/`): the only validator differences are the four CP pill
wraps gone; qa_all GATE PASS.

### 2026-09-17 — The ILS DDA count is saved from Charles's weekly email automatically

Aaron: "Update the ILS DDA count from Charles's email with subject 'ILS Management Server DDA
Count'. Our CSI Email Monitor task can do this as part of its checks." `scripts/ils_dda_count_mail.py`
takes the newest such email (from charles.baker or velocityalerts) out of Outlook over COM and saves
its body as `Inputs/CashPlease/ILS-DDA-Count-<sent date>.txt`, the file `build_cashplease.py` reads
for the loans-per-DDA denominator. The CSI Email Monitor's runner calls it before its Claude step,
so the ~280 counts are copied, not retyped by a model. It saves only a body that parses to a table,
and a week already saved with a different table is reported and left alone (compared as parsed
counts, so `&amp;` versus `&` in a client name is not a difference). 2026-09-17 saved: 232 clients
with a count, 45 NULL.

### 2026-09-17 — A branch-name dataset in Inputs, kept by the morning source check

Aaron: "create a branch mapping data set in inputs and update it when new branch names are
discovered." `Inputs/Branch Names/branch_names.csv` holds one row per name a source has given a
client's branch number (client, number, name, source, source file, first and last seen); nothing
is removed. `watch_sources.py --branch-names` (now in the scheduled task) adds names from each
client's Charts workbook, Branch Results tab, and from the ICS referrals pull's VIP branch names.
A Charts file is tied to a client only when exactly one client's whole name fits its filename
("federal credit union" read as FCU, "credit union" as CU); the rest are reported for a row in
`charts_files.csv`. `branch_names.client_map(id)` reads it back: the Charts name wins, VIP fills
numbers the Charts file lacks, and a number one source names two different ways is left unnamed
("North Shore" and "North Shore Branch" count as one). First run: 1,638 names for 78 clients;
Marine FCU gets names for all 18 branch numbers its ODD uses, where its Charts file had 15.
Nothing in the monthly decks reads it yet. Tests: `tests/test_branch_name_dataset.py`.

### 2026-09-17 — The morning source check keeps the ICS referrals query current

Aaron: "For the ICS query we need to pull that list periodically. Automatically update the query
during the morning file scan to only pull from the last scan to now, then dedup any overlap."
`watch_sources.py --ics-referrals` (now in the scheduled task) runs `scripts/ics_referrals_pull.py`:
each result saved as `Inputs/ICS Referrals/ics_referrals <date>.csv` is merged into
`ics_referrals.csv`, and `ICS Referrals - new since last pull.sql` is rewritten with `@since` set
to the day of the newest referral merged. Overlap is removed per referral (client, account, issue
date): the newer pull's rows replace the older's, which also keeps the query's branch-join
duplicates from stacking up across pulls. A result whose header or column count is not the
query's (SSMS does not quote a comma in a name) is reported and not merged. The query moved into
the repo as `scripts/sql/ics_referrals_all_clients.sql`. Tests: `tests/test_ics_referrals_pull.py`.

### 2026-09-16 — CSM Sheila shows what's new and links the change log

The page header has a "What's new" menu with the five newest entries of this file (date, title and the first
paragraph) and a "Change log" link to the whole file, rendered at `/changelog` (Aaron: "Add a link to the
change log at the top of Sheila's page, and show the last 5 updates"). `release_launcher.ps1` now copies
`CHANGELOG.md` beside the released code so the page reads the released version.

### 2026-09-16 — Contact Us card names the managing CSM; ICS Direct Mail New Accounts slide

**Contact card** (Aaron: "The contact card should always show the managing CSM"). Every deck's Contact Us
card was one CSM's static card: the ARS, MRPC and CashPlease template shells carried it and the builders
kept it, and ICS read it from the sheet. The card is now the client's managing CSM (`Client CSM List.csv`),
with that CSM's row in `CSM Contacts.csv`, resolved by `rpe_env.csm_contact` and written into the shell
cards by `shapes.fill_contact_card`. A CSM with no phone gets no phone line. A client with no CSM, or a CSM
with no row, stops the build rather than falling back to another CSM. Standalone ICS decks always carry the
Contact slide and add the ICS program contact, Cindy Draper, as a second card (Aaron: "Add Cindy on ICS";
her row added to `CSM Contacts.csv`); combined decks keep the base program's single card. The 24 2026.09
ARS decks in Outputs for other CSMs' clients carried Aaron's card and were rebuilt.

**ICS direct mail** (Aaron: "Direct mail should get its own slide"). A sheet's `direct_mail` block (from
`Inputs/ICS Direct Mail/`) renders as "Direct Mail New Accounts" after Results by Branch: a monthly chart,
program-to-date and latest-month callouts, and the top branches. Those accounts are a different channel and
are never added to referral figures (1776 CoastHills CU: 384 accounts, Apr'25 – Aug'26). VIP decks without
direct-mail data are unchanged (1676, 1549, 1075 rebuilt before and after).

### 2026-09-16 — ICS section from local files when there is no VIP sheet (1776 CoastHills CU)

New `build/ics_pipeline/ics_local_sheet.py` builds the ICS client sheet from the referral detail export
(`Inputs/ICS Referrals`), the current-period ICS workbook, the ICS Charts Goals tab and the direct-mail
list (`Inputs/ICS Direct Mail`, recorded, not rendered). `build_month.build_client` falls back to it only
when the VIP sheet is missing; what the files cannot supply (month to date, mystery shop, referred
accounts by product, contacts) is omitted, never zeroed, with the reason in the sheet's provenance.
`build_ics_gen` notes name those files and say "not VIP", the date pill uses the last referral date, and
goal tiles and columns are dropped when no goal is on file. VIP decks are unchanged (1676 and 1549
rebuilt before and after, identical). New `rpe_env.INPUT_KIND_DIRS` kinds `ICS referrals` and `ICS
direct mail`, both unscanned (hand-landed, member-level). The legacy `.xls` referral export is read with
xlrd or, without it, an Excel-converted copy in `Build Artifacts/ics_local_sheet/<id>/`.

**Fix (every ICS build):** a full ICS build with no Contact slide wrote `slide27.xml` twice — the Summit
slide took a static slide's part name, which the package check caught on 1776. Slide parts are now
renumbered before the Summit is inserted; `tests/test_ics_local_sheet.py` pins it.

Open for Aaron (1776): the Charts Goals Total row says 48/month but the branch goals sum to 80 (80 used);
169 pre-2025 referrals on the Charts tab are not in the referral file; the workbook's 2,575 accounts do
not reconcile to 2,280 referrals + 384 direct-mail accounts; whether direct mail gets its own slide.

### 2026-09-16 — CSM Sheila offers an ARS-only or a combined deck; 1776 is on ICS

**Two builds** (Aaron: "add a second Create button so the CSM can elect to build an ARS only deck, or a
combined deck for whichever products have the appropriate data"). `ars_launcher.program_availability`
decides, per clients.md program, whether its data is on hand this period: ICS from its VIP sheet or,
without one, the local ICS workbook and referral files (`ics_local_sheet.available`); MRPC from its
VIP sheet. When any is available the client page shows a second button, "Build combined (ARS + …)",
which runs `ars_launcher.py build <id> --combined`; programs without data are named as left out.
Any CSM may now choose a combined deck; for Aaron's multi-program clients the combined deck is the
only build offered (an ARS-only deck must not replace his combined one). A combined deck also passes
the package-integrity check before it goes to Outputs, and delivering either kind archives the
client's other ARS-bearing deck for the month, so a client has one deck per period.

**1776 CoastHills CU is on ICS** in clients.md (Aaron: "Add ICS, but don't pull from VIP"), built from
James Gilmore's ICS workbook, referral detail and direct-mail files rather than a VIP sheet.

### 2026-09-16 — The last two build files left in the temp folder are removed too

A 1539 Marine FCU build died in `build_ars_gen.py` with "OSError: [Errno 28] No space left on
device" while saving its phase deck, with C: at about 6 MB free and several ARS builds running.
The fix below covered the scratch *directories*, but two scratch *files* were still written
straight into `%TEMP%`, where `temp_dir` never sees them and `sweep_temp` (directories only)
never removes them:

- `build_ars_gen.py` copied the template shell to `%TEMP%\_<id>_ars_work.pptx` and never deleted
  it. It now lives in the build's `ars_assets_` scratch dir, removed at exit.
- `build_cp_gen.py` saved `<deck>.__full.pptx` to `%TEMP%` and deleted it only if `strip_dead.py`
  succeeded, so a failed strip left it behind. It is now written inside a `TemporaryDirectory`
  block, removed however the block ends.

`tests/test_temp_cleanup.py` only looked for `tempfile.mkdtemp(`, which is why neither was caught.
It now also fails on `mkstemp`, `gettempdir()`, `NamedTemporaryFile(delete=False)`, a
`TemporaryDirectory` outside a `with` block, and `extractall` (whole-zip extraction) anywhere in
`build/` or `scripts/`; and it checks that the extracted ODD is gone once the process exits and
that both `resolve_csv` functions go through `rpe_env.extract_odd_csv`. Path-only change: no
slide, figure or source note moves.

### 2026-09-16 — Build scratch is removed; every build sweeps the temp folder first

The C: drive reached 0.11 GB free and two Reg E rebuilds (1192, 1554) died with "No space left on
device". Every ARS build unzipped the ODD extract (up to 1.8 GB, plus the month's transaction file
beside it) into `oddd_*` / `oddcsv_*` folders and rendered images into `ars_assets_*` /
`ars_phase_*`, and none of them was ever deleted: 1,241 folders, about 180 GB, back to 2026-08-31.
They were cleared by hand (older than 2 hours only).

- `rpe_env.temp_dir(prefix)` is now the only way the pipeline makes build scratch; it is removed
  when the process exits.
- `rpe_env.extract_odd_csv` extracts only the ODD member of the zip, not the transaction file.
- `rpe_env.sweep_temp()` removes pipeline scratch older than 6 hours (left by a crashed or killed
  build); `build_month.build_client` — and so `ars_launcher` and CSM Sheila — run it first and log
  what they removed (Aaron: "make sure temp drive cleanup is part of the process").
- `tests/test_temp_cleanup.py` fails if any build or scripts file calls `tempfile.mkdtemp` directly.

### 2026-09-16 — Reg E opt-in read as zero for "Opted In / Opted Out" extracts (correction)

**A client-facing number was wrong.** `metrics_gen.regd` recognised only "opt in / opt-in / optin",
so extracts worded "Opted In" / "Opted Out" put every open personal card holder in "no election".
1776 CoastHills shipped Reg E opt-in at 0.0% on all five Reg E slides and Program Overview (the
extract's latest month has 12,967 opted in, 30,941 opted out, 8,892 default); James Gilmore's deck
for the same client showed 21.1%, which is how it surfaced. `oddd_optimize.classify_rege` read the
same files correctly: two definitions of one rule that had drifted. 16 decks in Outputs carried a
misread Reg E base: 1038, 1192, 1217, 1520, 1537, 1542, 1554, 1652, 1673, 1745, 1759, 1765, 1766,
1776, 1798, 1799.

**Fix.** `build/ars_pipeline/odd_rows.rege_label` is now the one reading, used by both. New wording
mapped with Aaron (2026-09-16): Yes/Y → Opt In; No/N, Revoked → Opt Out; Failed to Respond, No
Decision, Did Not Reply, D → Default; Ineligible, Exempt, "Tracking Type N Does Not Exist", "No
Vaule - No Reg E", "Anything else" → not applicable.

**The check that would have caught it.** `metrics_gen` now stops with a POSSIBLE DATA ISSUE when the
latest Reg E column carries wording no mapping covers, instead of counting it as no election; and
`tests/test_rege_label.py` fails if either file carries its own wording rule again. The synthetic
fixture's unmapped "Undetermined" became "Opted In" (unmapped handling is tested directly).

### 2026-09-16 — ARS Revenue Lift Matrix drawn as a heat grid; caption example is 1-5 → 11-15

**What the slide renders changed (every MM deck).** `render_lift.py` drew two plain tables (the matrix
and the Revenue Segmentation block). It now draws the matrix as a heat grid in the house chart style,
with impossible moves shown as a dash, and the segmentation block as bars of monthly value per card
account with each tier's share of cards (Aaron: "swap the heat grid into render_lift.py for all MM
decks"). No figure moved: both halves read the same lift.json as before, at the slide's picture aspect.

**The caption's worked example changed** (Aaron: "use 1-5 to 11-15 as the example in the bottom
text"). It was Non-User → 26+ written as an equation; it is now "a 1-5 account ($x a month) that moves
to 11-15 ($y) adds $z a month", and that cell is outlined orange on the chart. `render_lift.example_move`
is the one definition; a matrix without that cell falls back to its largest move. `render_lift.py` is
import-safe now so `build_ars_gen` can share it. Tests: `tests/test_render_lift.py`.

**No selection line on the slide** (Aaron: "remove the selection text on the lift matrix slide"). The two
chart titles inside the picture say what the grid and the bars show, and the window is on the pill; the
template's subtitle shape is removed, not blanked, and the build stops if it cannot be found.

**The browser builder is CSM Sheila, the Smart Helper for Executive Insights, Layouts & Analytics.** WILL was renamed again the same day; `ARS Deck Builder GUI.bat`
still starts it.

### 2026-09-16 — The browser builder is WILL; a failed build shows a red Error pill

**Name.** ARS Deck Builder is now **WILL, the Workbook Intake & Layout Launcher** (Aaron). Its
launcher file is `ARS Deck Builder GUI.bat`; the old `ARS Deck Builder.bat` on the share was moved to
`Tools\_retired launchers - delete after review\`. The page title, header, console window and user
guide carry the new name.

**Error pill.** When a client's last build for the cycle was not put in Outputs, the client list
shows a red **Error 2026.09** pill (the cycle period) and the client's button reads **Retry build**
(or **Retry rebuild** when a deck is already in Outputs). `last_build_failed` decides it: a job this
server ran and still remembers wins (running or queued is never an error); otherwise the launcher's
`_launcher_result.json` for the period, unless a deck for the period reached Outputs after that record
was written. On the first run it flagged 1121 Timberland, 1615 Cape & Coast and 1748 Clearview.
A failed build followed live also turns its button back on as Retry. No deck output changes.

### 2026-09-16 — ARS Deck Builder: a second build queues instead of being refused

Starting a build while another ran on the same PC returned "A build for … is still running. Start the
next one when it finishes", so a CSM had to watch for the first to end. `start_build` now puts the job
in a first-in, first-out queue and one worker runs them one at a time, as before. The client list
polls `/api/queue` every 3 seconds and shows **Building** on the running client and **Queued #N** on
each waiting one, where N is its place in the line. A queued client's page and button say the same.
Asking to build a client that is already building or queued still returns 409. No deck output changes.

### 2026-09-16 — ARS Deck Builder: Full output stays open, shown as a terminal

Clicking "Full output" during a build opened the panel for at most 1.5 seconds: every
job poll rebuilt the whole build area with `innerHTML`, which replaced the open
`<details>` with a closed one. `renderJob` in `scripts/ars_launcher_web.py` now creates
the panel once per build and afterwards only updates the step list and the output
text. The open state survives switching clients, and the output stays scrolled to the
bottom unless someone has scrolled up. The output is drawn as a Windows Terminal
window with `[ok]`, `[!!]`, `[built]`, `[STOP]` and `[..]` in color. No deck output changes.

### 2026-09-16 — CashPlease inputs have their own folder

**CashPlease data now lands in `Inputs/CashPlease/`** (Aaron: "add inputs folder for CashPlease
data"). Bradford Sanders' CashPleaseSummary weeklies and the weekly `ILS-DDA-Count-<date>.txt`
used to share `Inputs/Weekly Summaries/` with the MRPC enrollment weeklies. The folder is the new
`"CP weekly"` kind in `rpe_env.INPUT_KIND_DIRS`. `mail_sources` files a CashPleaseSummary
attachment there, and still keeps only the newest. `build_cashplease` and the dashboard refresh
already search every scanned input folder, so they find it unchanged; their "save it here"
messages and the dashboard's source line name the new folder. The per-client production settings
stay in `Inputs/Product Settings/`, which is the Velocity Product Settings app's folder rather than
a CashPlease one. The two CashPlease files already on hand were moved, not copied.

### 2026-09-15 — the archive is `Outputs/_Archive/`

**`Outputs/Archive/` is renamed `Outputs/_Archive/`** (Aaron: "add to the archive folder names so they
stay at the top, above my name"). "Archive" sorted between "Aaron Burgard" and the other CSM
folders. The underscore puts it at the top of Outputs, beside `_Unassigned`. The name lives in
`rpe_env.ARCHIVE_DIRNAME`, which `promote_month` and `ars_launcher` archive into.
`output_decks` skips both the new and the old name, so a leftover `Archive/` is never read as a
CSM's folder. The folder on the share was renamed, not copied. `tests/test_archive_dirname.py`
covers the name, the skip of both names and the two writers.

### 2026-09-15 — client logos were clipped on the slide

**`rpe_env.trim_logo` cut into 26 of 122 client logos** (Aaron: "CoastHills needs a corrected
logo"). The logo file was fine. The CoastHills site's SVG renders pixel-identical to
`Inputs/Logos/1776.png`, but the deck's agenda slide carried a 1600x294 slice of the 1600x384 logo,
with the tops of the letters gone.

The cause: a transparent logo whose artwork touches the canvas edges has a full-canvas alpha box.
trim_logo took that as an opaque canvas, sampled the border (the lettering itself) as the
background colour, and subtracted it. The worst cases kept a fragment: 1183 came out 632x28,
1072 133x134 of 1195x258, 1526 166x166 of 1200x437, 1204 320x314 of 1200x314. The opaque-canvas
pass now runs only when at least 90% of the border ring is opaque. Those 26 now keep their full
artwork, and the other 95 trim exactly as before, including the white-canvas logos the pass exists
for (1549). `tests/test_trim_logo.py` covers the opaque canvas, transparent padding and the
edge-to-edge transparent logo.

Decks built before this carry the clipped logo until they are rebuilt. 2026.09 decks in Outputs
affected: 1156, 1204, 1218, 1673, 1734, 1759, 1776 and 1798.

### 2026-09-15 — the issue pages are built from the repo

**The ODD and Workbook Issues and CSM Data Gaps pages are now built by `scripts/issue_pages/`**
(Aaron: "move the issue page scripts into the repo"). They had been built from scripts in a Claude
session scratchpad, with the share and the repo checkout written into them. Every path now
resolves through rpe_env (`common.py`). Working data and both pages live in `Build Artifacts/issue_pages/`,
because they carry client names and products. `build_issue_pages.py` runs the chain in order and
copies both pages to `Notes/`. `tests/test_issue_pages.py` fails on a written-in share or machine
path, and covers the share-history scan and the Notes charset.

What changed on the way in:
- `missing_wb_history.py` is new. Nothing in the scratchpad had written that file; it scans every
  month on the client-reports share for the Missing Workbook clients.
- The ODD page no longer carries a separate "Missing Workbook" table above the CSM sections. A
  Missing Workbook client is listed in its CSM's section only (Aaron: "Jordan's missing Texar
  workbook should be in his section").
- Stale one-day patches came out: the "recalculated, rebuild in progress" note for 1192 and 1673,
  the hand-added uncalculated-workbook finding for 1673 (it has since built clean) and an empty
  ARS-confirmed override. The Data Gaps page drops from 120 to 119 issues as a result.
- "September" and the 20-client roster count are derived from the period and clients.md, not
  written in.

### 2026-09-15 — an expired Lift Matrix stops the launcher's build

**The launcher now checks the Lift Matrix before an MM client's build** (Aaron: "flag it as having
an expired lift matrix. Add the lift matrix date check to the build criteria"). It stops when the
workbook's data month is past the Lift Matrix MM End Date. It also stops when the workbook filename
carries the data team's flag ("LM EXPIRED", "NEEDS LIFT MATRIX", "NEW LIFT MATRIX NEEDED"; the
same `perf_actions.lift_matrix_flag` the performance page uses). The fix it names is the CSM's: a
new Lift Matrix. SM clients have no Lift Matrix and are not checked. `status`, `build` and ARS Deck
Builder all run it. The builder's client list tags an expired matrix "Lift Matrix expired", read in
the background when the builder starts.

The window reading moved out of `extract_lift.py`, which runs as a script, into import-safe
`build/ars_pipeline/lift_window.py`. The launcher reads the same definition the deck does.
extract_lift's output is byte-identical on 1780, 1441 and 1520. On the 2026.09 batch the dates
expire seven MM clients: 1453, 1487, 1526, 1529, 1637, 1681 and 1780. Five of those workbooks were
already flagged by filename. 1526 and 1681 were not flagged, but their windows ended May 2026 and
Feb 2026.

**The six 2026.09 decks already in Outputs on an expired matrix were taken out of Outputs**
(Aaron, 2026-09-15: move all six): 1453, 1487, 1526, 1529, 1681 and 1780. Each is in
`Outputs/Archive/_older decks - delete after review/<CSM>/<id> <client>/`, named "(expired lift
matrix 2026-09-15)". Nothing was deleted. They are rebuilt once a new Lift Matrix lands, and until
then the launcher refuses to build them.

**The launcher and the builder name a client from `clients.md`**, as its deck does. The Client CSM
List name comes from a workbook filename and had picked up the flag: 1780 read "LM EXPIRED-USF CU /
USF CU". That list entry is now "USF CU" (backup in `Build Artifacts/`). The builder's list also
drops the program tags and dates its Outputs tag: "In Outputs 2026.09".

**ARS Deck Builder caches what it has checked** (Aaron: "can we speed up the UI by caching
information?"). A client's status cost 3-6 seconds, mostly the share and Inputs checks (about 2s)
and opening the workbook for its Lift Matrix (0.4-2s). Now:
- each status is kept for 10 minutes, and the page says how old it is;
- "Check again" re-reads it, and a finished build drops that client's entry;
- every client is checked once in the background when the builder starts, so a click is usually
  instant;
- the launcher remembers each workbook's Lift Matrix window until the file changes.

`ars_launcher.py build` never uses the builder's cache: its checks run fresh right before the build.

**A deck already in Outputs asks before it is rebuilt** (Aaron: "The deck is already in Outputs, but
it says Build and put in Outputs. It should ask if we need to rebuild"). The rebuild question used
to follow the delivery log, and only Aaron records sends, so another CSM's client with a deck in
Outputs (1815 FedChoice) was offered a plain build. It now follows Outputs: any ARS-bearing deck
for the client and period in any CSM folder. The builder says "This month's deck is already in
Outputs", the console marks it `[built]`, and the .bat asks "Rebuild it and replace it".

**The launcher no longer tells anyone to mark a deck sent** (Aaron: "the other CSM don't have an
artifact to mark those, and i don't have to do that part for them"). The builder's "Sent" chips,
its "tell Aaron it went out" line, the console's "Mark it sent" line and the user guide's step are
gone. Rebuilding a deck already recorded as sent still asks first. Only Aaron's decks are ever
recorded, so other CSMs never see that question.

### 2026-09-15 — ARS Deck Builder: the launcher in a browser

**`ARS Deck Builder.bat` opens the ARS launcher as a page in the browser** (Aaron: "would it be
possible to run Build ARS Deck.bat in an application or browser?"). A browser cannot start a
program, so the .bat starts `scripts/ars_launcher_web.py`, a small server on 127.0.0.1, and opens
its page. The page lists the `clients.md` ARS clients by CSM, with sent and in-Outputs chips.
Picking a client runs `ars_launcher`'s own `rule_checks` and `input_checks`. The button is Build,
Rebuild (after a second click, when the deck was already sent), or Check again when something
stops it. The build is `ars_launcher.py build` run as a child process, and its step lines are
shown as they arrive. A finished deck gets a "Show it in File Explorer" link. The rules, the build
and the delivery to Outputs are unchanged, because the page only calls the launcher. One build
runs at a time per PC.

Only the page this server served can use it: every API call needs the random token baked into
that page and a 127.0.0.1 or localhost Host header, so another site open in the same browser
cannot start a build through localhost. The reveal call opens only a file under Outputs.
`Build ARS Deck.bat` stays as the plain-console fallback. `tests/test_ars_launcher_web.py` covers
the token and Host checks, a bad client number, a build job's lines and deck, the
one-build-at-a-time rule, and the Outputs-only reveal.

### 2026-09-15 — the MM lift matrix slide is titled "ARS Revenue Lift Matrix"

**The MM slide is now titled for what it shows** (Aaron: "This slide should be titled ARS
Revenue Lift Matrix"). It still read "Monthly Summary — Last 12 Months" over a lift matrix
table, because on 2026-08-20 both revenue models kept one title. That decision is reversed for
the MM path only. The SM slide is a 12-month revenue chart and keeps its title. The ARS agenda
line on MM decks names the slide the same way. The speaker note now sources the Lift Matrix
MM tab, because `_note_for` matches "lift matrix". The banned-word check already allows "lift"
inside the named Lift Matrix slide. The date pill still shows the matrix's own 12-month window
from the workbook's Start/End cells.

**The delivered 2026.09 MM decks were rebuilt with the new title** (Aaron: "put it in Outputs as a
v2, then fix the other decks"). Each ARS deck was re-assembled from its batch's staged metrics,
charts and extract; the inputs had not changed, only the builder. Aaron's combined clients were
re-assembled with the ICS section they shipped with. A deck already recorded as sent (1509, 1537,
1676, 1705), and 1539 as asked, went in as "<name> v2.pptx", with the deck it replaced moved to
Archive. Every other deck replaced its copy through `promote_month`. SM decks (1038, 1156, 1652)
have no lift matrix slide and were left alone. The original 1539 deck stays beside its v2 until
the person who has it open closes it.

**1676 True Sky was rebuilt in full on a re-pulled ODD** (`1676_ODDD_Code updated.zip`, 09/15
13:13). It carries the same 52,848 rows and columns as the 09/01 pull. The difference is the 6 open
accounts whose `Business?` flag was blank (product codes CBMM and BMM1); all 6 now read "Yes".
The zip also drops the monthly debit-card transaction file, which no reader opens: every reader
takes only the `.csv` member. The source watch did not copy it, because its name does not match
`<id>_ODDD.zip`; it was copied into `Inputs/ODDD/1676_ODDD.zip` by hand. The v2 built from it
replaced the title-batch v2 built on the old extract.

### 2026-09-15 — the four-program agenda hid its "1"

**Row 1's number was drawn under an orange circle on the Marine FCU 1539 ARS-ICS-MRPC-CP deck**
(Aaron: "the first bullet on the Agenda is missing the number 1"). The template's agenda has
four rows, so a fourth program clones a fifth. `set_agenda` cloned the number, then the badge
circle, so the circle sat above its number. During layout it then looked each row's circle
up by position. A clone sits exactly on its source until it is moved, so row 5 found ROW 1's
circle and carried it down. The clone's circle stayed on row 1, covering the "1". The clones
also kept their source's shape ids (119-122 twice on one slide). Each row's circle is now
resolved once, before cloning, and moves with its row. A clone's circle is cloned before its
number, and `_clone` gives every copy a new shape id. Only 1539 was affected: every other
combined deck has four rows or fewer and never clones. A new test assembles a four-program
agenda and checks that every number shows, sits on exactly one circle, and that no shape id
repeats. No earlier test assembled more than three programs.

### 2026-09-15 — 1615's empty debit-usage base stops with a named cause

`metrics_gen` averaged spend over the card holders who swiped in the latest month, for new
accounts and for the open book. 1615 Cape & Coast has no such open card holders: 18,912 personal
accounts carry Stat Code `0` with a blank Stat Desc, so only 720 read as open, and none of
those 287 card holders swiped in Aug26. `mean()` of nothing crashed the build with a
`StatisticsError` that named no cause. It now stops with POSSIBLE DATA ISSUE, giving the counts
and the most common status values on accounts that don't read as open. `0` is not mapped: it
is a code-sheet correction for the client, already on the Data Gaps page.

### 2026-09-15 — an ARS deck can be built without Claude

**`Build ARS Deck.bat` in the CSM_Reporting folder** (Aaron: "i'd like to develop a way where
anyone can run an ARS deck so long as the inputs are in place"). It asks for a client number
and runs `scripts/ars_launcher.py`, which applies the checks that used to be done by hand, all
of them BEFORE the build:

- the client is on the Client CSM List, its product list includes ARS (a blank list warns),
  and `clients.md` lists it for ARS;
- a client of Aaron's on more than one program stops, because it ships a combined deck;
- a deck already marked sent for the period is a question, not a stop (Aaron: "can the script
  prompt whether the user wants the presentation re-run rather than failing?"). `status` exits
  3 when that is the only thing in the way, and the .bat asks "Rebuild it and replace the one
  in Outputs". On the command line it takes `--rebuild`;
- the ODD extract and ARS workbook are there and current for the cycle period (the newest ARS
  workbook in `Inputs/`), through the same `deck_status.requirements` the dashboard uses. A
  missing DCO warns. A stale or missing input stops with the fix named for the data team;
- one build per client at a time (a lock in the work folder, taken over after 3 hours).

The build works in `Build Artifacts/launcher/<period>/<id>/`, where its log, charts and data stay
out of sight. A deck that validates with 0 FAIL goes straight to `Outputs/<CSM>/`, and what it
supersedes is archived by `promote_month.promote_one`. If the Outputs deck is open, nothing
moves and the launcher says to close it. There is no staging folder and no separate deliver
step. A `Staging/` folder and a `Deliver ARS Deck.bat` with a typed-YES prompt were built and
dropped the same day (Aaron: "Each CSM will manually review, PDF, and email these
presentations. We can skip staging altogether and go straight to Output.").

The build's own output goes to `build.log`, so the launcher watches that log and prints each
step as it starts. Without that, the window sat silent for up to 15 minutes.
`ARS Deck User Guide.html` sits beside the .bat file.

That exposed a `build.log` defect that affects every build, not only the launcher.
`build_month.run` wrote each step's command line without flushing before the step started, and
the step writes straight to the file. So each command line landed AFTER its own output. A
traceback therefore read as belonging to the step before: 1615's metrics_gen error sat under
the oddd_optimize command. It also meant the launcher named each step when it ended. `run` now
flushes first, and a test checks the order.

`scripts/release_launcher.ps1` copies the code to `Tools\RPE` on the share and, with `-Runtime`,
a zipped Python with the libraries that each PC unpacks to `%LOCALAPPDATA%\RPE` on first use.
The launcher runs the released copy, so a change in the repo reaches it only after a release.
`tests/test_ars_launcher.py` covers the rules.

### 2026-09-15 — the archive is filed by CSM

**`Outputs/Archive/` now has a folder per CSM, like `Outputs/`** (Aaron: "sort the archive by
CSM"). A superseded deck goes to `Archive/<CSM>/<id> <client>/`, and older decks of the same
period and kind go to `Archive/_older decks - delete after review/<CSM>/<id> <client>/`.
`promote_month.client_folder` takes the CSM from `rpe_env.client_csm` (else `_Unassigned`) and
still reuses an existing client folder wherever it is, including a flat one from before. A
rolled-back delivery removes the CSM folder it created if it is left empty. The existing
client folders, 15 in Archive plus those in the review folder, were moved, not copied. Nothing
was deleted. Folders for Max Willett (a CSM with no accounts yet) were created in `Outputs/` and
`Outputs/Archive/`.

`tests/test_promote_month.py` checks that archiving files under the CSM, that an existing
CSM-filed folder is reused, and that the review folder mirrors the CSM layout.

### 2026-09-15 — CSM action items on the performance page

**A new first section lists what a CSM has to take to the client** (Aaron: "If we have unmapped
values for current ARS clients the CSM needs to contact the client to get those fixed. The CSM
also needs to create a new lift matrix if the current one is out of date."). It covers current
ARS clients and follows the CSM, product and client filters.
- **Lift Matrix out of date** is the data team's flag in the ARS workbook's filename ("LM
  EXPIRED", "NEEDS LIFT MATRIX", "NEW LIFT MATRIX NEEDED"), as Aaron chose over the Lift Matrix
  tab's end date. On 2026.09: 1453, 1529, 1780, 1487, 1637; 1743's flag is on its 2026.08 workbook.
- **Codes not mapped** compare each client's ODD (Prod Code, Stat Code, the newest `<Mon><yy>
  Reg E Code` column) with that client's code tables in the ARS database. The terms are the VIP
  Data Specification's: "Product Codes not mapped", "Product codes with no Personal/Business
  flag" (a listed product code whose `is_business` is blank; Personal/Business is set per
  product code, Aaron), "Account Status Codes not mapped", "Mail Flags not mapped" and "Reg E
  Codes not mapped". The ODD carries no raw mail code, only `Mailable?`, which the database has
  already mapped, so a Mail Flag is flagged when that value is anything but Yes or No. Product
  and Account Status decide ARS eligibility, so those items list first and say so. Mail Flag
  decides who is mailed, not eligibility: on 12 clients about 99% of otherwise-eligible
  Mailable?=No accounts are Elig=Yes (1075 514 of 514). Reg E decides neither (Aaron). Each value shows its account count. **Nothing is mapped:** a CSM has the client correct the code
  sheet; no value is added to `STAT_CODE_MAP` or the Reg E classifier (Aaron: "don't force any
  mapping").
- **What cannot be checked is said.** No ODD extract, no code tables, or a column the extract
  lacks is written on the row, never read as "all mapped". A client with no table of a kind in
  the database gets every value listed with a "no table" tag.
- **Where the tables come from.** `scripts/ars_code_tables.py` reads the ARS database export
  (SQL Server text output) and writes only the product, Reg E and status code tables to
  `Inputs/ARS Settings/ars_code_tables.json` (new rpe_env kind "ARS codes", not scanned). The
  clients' code sheets themselves go in `Inputs/Code Sheets/` (kind "Code sheets", also not
  scanned, so the watch and the pruner leave it alone). The
  export's client SETTINGS table carries plaintext FTP passwords and salts: tables are found by
  their id column and only named columns are read, so it is never parsed past its header, copied
  or committed. The mail code table is left out; the ODD has no raw mail code to check against it.
- **No extract is read twice.** The codes are counted in the Client overview's pass
  (`perf_overview`, cache version 3, so every extract is re-read once) and dropped from the page
  data after the check.

### 2026-09-15 — an ARS workbook a month behind is shown the same way for every client

**Seven clients lost their ARS row for want of this month's workbook** (Aaron: "if that's the
case for austin isn't the same with others? make sure that behavior is consistent"). 1075
Austin Bank has no 2026.09 ARS workbook on the share. It is on the clients.md roster, so the
page showed its 2026.08 workbook tagged "workbook 2026.08". A client not on the roster had its
programs inferred from THIS month's share files only, so 1100 Rally, 1121 Timberland, 1126
Legend, 1147 Sutton, 1403 Adirondack, 1554 Isabella and 1743 Mid American all had a 2026.09
DCO, a 2026.08 workbook in Inputs, and no ARS row at all.
- **The rule now.** `page_clients` also puts an inferred client on ARS when Inputs holds its
  ARS workbook from the last two months (`ARS_WORKBOOK_LAG`). The row carries that workbook's
  period and the page tags it, exactly as for Austin Bank. An older lone workbook (the pruner
  never removes the last one) does not bring a client whose ARS ended back onto the page.
- **MRPC rows get the same tag.** A row whose VIP sheet is for an earlier period than the
  cycle now says "VIP <period>". ICS and the Client overview already tagged theirs;
  CashPlease and the MRPC weekly always use the newest weekly by design.

### 2026-09-14 — the performance page drops its subheading

**The line under the title is gone** (Aaron: remove "85 clients, 5 CSMs, across four programs.
Click a CSM, product or client to show only that one, click others to add them, or click All
for the whole row."). The element and the two script lines that filled it are removed. The
"How the decks are made" link stays in the header.

### 2026-09-14 — the performance page's summaries cover current clients only

**The CashPlease peer row is rebuilt over current clients** (Aaron: "For any of these summary
sections, or the client's statistics, only show current clients"). It was
`cp_extract`'s rollup of every tab in the weekly workbook, and on 2026-09-14 51 of those 72
client tabs were not current clients.
- **How it is built.** `refresh_performance_dashboard.current_peer` uses `cp_extract`'s
  formulas on the current clients' own packs. Cancelled programs and tabs with no loans are
  left out. Summed over every tab, those formulas reproduce the rollup's loans, average loan
  size and interest, and status shares.
- **What is left blank.** Charge-off % and the share of active accounts with loans are values
  the workbook reports, and no weighting of the per-client values reproduces them (the
  rollup's 6.26% against 4.72% principal-weighted, for example). The row shows them as absent,
  not approximated.
- **The decks are unchanged.** The CashPlease decks' own peer slide still uses the rollup.

**A program with no activity in six complete months is no longer shown as current.**
`inactive_since` looks at the six months before the weekly report's month: loans for
CashPlease, enrollments for MRPC.
- **Inferred from data.** The program is dropped and the refresh logs it. 1487 Orsa CU's
  CashPlease last booked a loan in Sep 2025.
- **Listed in `clients.md`.** The program stays, because that file decides, tagged "no loans
  since …". 1770 Central State Bank's CashPlease last booked a loan in Dec 2025.

### 2026-09-14 — the workflow page describes Outputs by CSM

### 2026-09-14 — an open account is open in any case, and by Stat Code when Stat Desc is blank

**`odd_rows.isopen`, which decides "open" for every ARS metric, disagreed with the two other status
readers beside it.** It matched Stat Desc case-sensitively and never read Stat Code, while
`odd_rows.status_class` (Product Mix, Excluded Accounts, the client overview) and `oddd_optimize`'s
classifier are case-insensitive and fall back to the code. In the all-client trial builds six clients
had no open account at all, and `metrics_gen` stopped with POSSIBLE DATA ISSUE:

- 1637 writes `open`, 1680 `ACTIVE` / `DORMANT`, 1759 `OPEN/ACTIVE`;
- 1743, 1746 and 1815 leave Stat Desc blank on every row and carry Stat Code `A` / `O`.

`isopen` now compares the description case-insensitively and, only when it is blank, reads the
Aaron-confirmed `STAT_CODE_MAP` (O / A = Open). An unmapped code (D, I, F, 0, word codes) is not
guessed open. `metrics_gen` now loads Stat Code.

**One delivered client's figures move: 1509 Texas Bay.** 1,755 of its accounts read `inactive` in
lower case. `Inactive` is in the open vocabulary, so the Product Mix slide already counted them open.
The ARS metrics did not, until now. The other roster ARS clients (1038, 1075, 1204, 1537, 1539,
1549, 1676, 1705) do not change by a single account. **1509's September deck has not been rebuilt.**

Still undecided and still stopping the build: 1226 (blank Stat Desc, word codes ACTIVE / DORMANT /
INACTIVE), 1585 (`File Maintenance` on 16,398 accounts and 11,396 blanks) and 1615 (18,912 blanks
with code `0`).

`tests/test_odd_rows.py` covers case-insensitive open and closed wording, the code fallback for the
confirmed codes only, the description winning over the code, and no fallback when Stat Code is absent.

### 2026-09-14 — a malformed ODD row is counted and flagged, and an empty base is named as a data issue

Found in the all-client ARS trial builds.

- **1147 Sutton died in `oddd_optimize`.** Three of its 28,930 ODD rows have one extra field,
  from an unquoted comma in a text cell. pandas keeps a row like that and shifts its cells,
  so "Customer Opt In" landed in `Sep23 OD Limit`. The fast (pyarrow) money path cast
  strictly and died, while the pandas fallback had always treated such a cell as missing.
  Both paths now agree: a non-numeric cell in a money or count column counts as missing, and
  the pack's `flags.non_numeric_cells` records how many there were and in which columns, so
  the defect is visible rather than silent. A well-formed extract gives identical figures.
  (`index_col=False` was tried first and does not stop the shift, so it was reverted.)
- **1226 Ellafi died dividing by zero** in the Reg E rate. Its Stat Desc is blank on every
  row, and the status is only in Stat Code (ACTIVE / DORMANT / INACTIVE), so no account read
  as open. **1121 Timberland died on an empty `mean()`**: its newer accounts carry numbers
  (`1`, `39`) in Prod Desc, so no new checking account was found. Neither is fixed by
  guessing. `metrics_gen` now stops with a `POSSIBLE DATA ISSUE` message that names the
  missing base and what the extract carries instead. Mapping word-valued Stat Codes is
  Aaron's call (CLAUDE.md: never guess a status mapping).

`tests/test_odd_malformed.py` covers the flagged non-numeric cells, a clean extract flagging
none, and both data-issue exits, all on the synthetic fixture.

### 2026-09-14 — Outputs is filed by CSM

**Finished decks now go to `Outputs/<CSM>/`, not the flat `Outputs/`** (Aaron: "sort the
Outputs folder by CSM"). The project covers all five CSMs' books now, and one flat folder
of every client's decks would not stay readable.

- `rpe_env.client_outputs(id)` is the one place the folder is decided. The CSM comes from
  `<RPE_DATA_ROOT>/Client CSM List.csv`, else the CashPlease roster's CSM column (the
  CashPlease-only clients 1131, 1564, 1750, 1770 and 1771 are not on the reports share the
  list is built from), else `Outputs/_Unassigned/`. It never guesses a CSM.
- `rpe_env.output_decks(pattern)` is how readers find decks. It searches every CSM folder
  and the flat root, never `Archive/`. `deck_status.built_deck` and b4's
  `refresh_performance_dashboard.decks_and_sent` use it; a reader left globbing the flat
  root would have shown every deck as not built.
- `promote_month` delivers into the CSM folder and archives a copy of the same deck still
  in the flat root, so a client never has a live deck in two places. `build_cashplease`
  writes into the CSM folder. `Outputs/Archive/` is unchanged, one folder per client.
- The 28 files already in Outputs (19 decks and 9 hand-made PDFs, all Aaron Burgard's
  clients) were moved into `Outputs/Aaron Burgard/`: moved, not copied or deleted.

`tests/test_outputs_by_csm.py` covers the CSM lookup, the Unassigned fallback, the roster
fallback, what the readers search (CSM folders and the root, not Archive, not lock files)
and the delivery dashboard finding a deck in a CSM folder. Two `test_promote_month` tests
now expect delivery into the CSM folder.

### 2026-09-14 — credit-union checking accounts count as checking

**`metrics_gen` found no new checking accounts at 1200 Guardians Credit Union and crashed.**
It counted an account as checking only when `Prod Desc` contained "checking". A credit
union's checking account is a *share draft* (Guardians: "Share Draft", "Share Draft
Aspire"), so the new-checking pool was empty and `mean()` of nothing stopped the build. The
match is now "checking" or "share draft", for both the new-checking pool and the top
checking product. **At a bank the figures do not change. At a credit union, the New Checking
Balances and debit-penetration slides now use its share drafts, where before they used
nothing or crashed.**

### 2026-09-14 — the MM extractor stops charting a blank Key Trends month as $0

**`extract_base_gen.py` turned a blank month into zero, silently.** It read each Key Trends
MM month as `round(spend.get(m, 0) or 0, 2)` and the card-holding count as
`(tot or 0) - (non or 0)`, so a month with no figures became $0 spend and zero
cardholders — a collapse on the Debit Card Swipes & Spend chart that nothing flagged. It
never crashed, which is why it went unseen; the SM extractor's version of the same read
crashed on 1657 and was fixed first (Aaron: "fix the extract_base_gen zeroing too").

- **One definition for both extractors.** `base_guard.key_trends` builds the 36-month
  series with a blank kept as None and its month listed, and `base_guard.data_issue`
  writes the POSSIBLE DATA ISSUE message. `base_tab_extract.py` now uses both instead of
  its own copy.
- **Same order as SM:** the unevaluated-workbook guard first, then any blank month stops
  the run with the workbook and months named and no `base.json` written.
- `extract_base_gen.py` is now import-safe (`main()`), with `extract()` and
  `dco_eligible()` testable directly; its output is otherwise unchanged.

`tests/test_extract_base_gen.py` pins None-not-zero, the data-issue exit, an uncalculated
MM workbook named as such, a populated workbook still extracting with its DCO, and that
neither extractor defaults a blank month any more.

### 2026-09-14 — SM builds had not been reading their DCO since the inputs were sorted

**Every SM (Monthly Summary) client has built without its DCO since 2026-09-09.**
`build_month.build_client` looked for the DCO with `glob(os.path.join(str(REPORTS), …))`.
`REPORTS` became a LIST of per-kind folders when Inputs were sorted by kind, and the string
of a list is not a folder, so the pattern matched nothing and `base_tab_extract` ran with no
DCO argument. Nothing failed — the DCO is optional to the extractor — so it went unseen:
1038 Sugar River's three staged builds on 2026-09-14 all carry `dco_eligible: null`. Found
while preparing staged ARS builds for every CSM's clients. No slide figure moves (the deck's
ARS eligibility comes from the ODD); the DCO's `Eligible ARS Accounts` now reaches
`base.json` again.

`build_month.dco_file()` searches every report folder, the same shape as `ars_workbook()`.
`tests/test_build_month_inputs.py` pins the multi-folder lookup, the period match, the
legacy folder, and that `build_client` no longer joins a pattern onto a list.

### 2026-09-14 — a blank Key Trends month is called out as a possible data issue, not a crash

**1657 Marine Credit Union's ARS extraction crashed, and the crash hid the real problem.**
`base_tab_extract.py` read each Key Trends month with `round(spend.get(m, 0), 2)`, which
defaults only a month that is ABSENT; a blank cell came back as None and raised
TypeError. The crash came before `base_guard`, so the performance page showed a Python
traceback for 1657 when the workbook was simply never calculated — one month, dated Sep
2007 (the template's), with no revenue: the same shape as 1192 Ascend and 1673
Neighborhood, which the guard did name (Aaron: "that should be called out as a possible
data issue").

- **Blank is None, never zero.** A blank spend or account cell now extracts as None and
  its month is listed in `key_trends_blank`; the old default would have charted a gap as
  $0 spend had the cell been absent rather than blank.
- **The guard runs first,** so an uncalculated workbook — the likeliest cause — is named
  as UNEVALUATED WORKBOOK with the Excel fix. 1657 now reports exactly that.
- **Any blank month left over stops the run** with `POSSIBLE DATA ISSUE: <workbook> has no
  Key Trends spend or card-holding figures for N of its last M month(s) (<months>)`,
  nothing extracted, so neither the deck builder nor the page receives a gap as data.
- The script is now import-safe (`main()`), so `extract()` is tested directly.

`tests/test_base_tab_extract.py` pins the None-not-zero extraction, the data-issue exit
(no traceback, workbook and month named), 1657's template shape reported as unevaluated,
and that a fully populated workbook still extracts.

### 2026-09-14 — the workflow page describes Outputs by CSM

**`workflow.html` now says decks go to `Outputs/<CSM name>/`**, where it used to say one flat
folder. The decks moved there the same day. The page's Outputs step, its "Writes" path and the
folder map follow the move, and the map names `_Unassigned/` for a client with no CSM. The
daily refresh does not republish this page, so the page was republished by hand.

### 2026-09-14 — the performance page finds decks in per-CSM Outputs folders

**`refresh_performance_dashboard.decks_and_sent` reads built decks through
`rpe_env.output_decks()` when rpe_env has it.** `Outputs/` is moving from one flat folder to
`Outputs/<CSM name>/` at Aaron's request. `output_decks` reads both layouts and never
`Archive/`. Before the helper exists, the refresh uses the old flat glob, which gives the same
answer. So the page's Deck and Sent columns stay right on both sides of the move. A test
covers a deck in a CSM folder with the helper, and the flat folder without it.

### 2026-09-14 — the Clients filter row folds

**The Clients row on the performance page is collapsible** (Aaron: "make the Clients filter
collapsible"). Across every CSM it runs to about ninety chips.
- **Closed by default**, and each viewer's open or closed choice is remembered.
- **The All chip stays visible**, beside a toggle. Closed, the toggle says how far the row
  is narrowed: "Show 85 clients", or "Show clients (3 of 85 selected)".
- **Unchanged:** narrowing works the same. The CSM and product rows still limit which clients
  the page shows.

### 2026-09-14 — ARS revenue to CSI on the performance page; totals before the month

**The two ARS callouts are replaced by ARS revenue to CSI** (Aaron: "we don't need
callouts for ARS incremental prof and ARS incremental revenue. I would like to see ARS
Revenue to CSI for the currently completed month (that's the ARS expense in the
workbook)").
- **The figure.** Executive Financials' "Total Costs" in the current-month Actual column,
  shown as a positive number. The ARS extractors emit it as `cur_costs`, and
  `refresh_performance_dashboard.csi_revenue` carries it.
- **Where it shows.** A summary tile, summed across the selection, and a "Revenue to CSI,
  current month" column in the ARS table.
- **What it includes.** For 2026.09, 1204 (Lift Matrix) reads $6,077.98 and 1038 (Monthly
  Summary) $5,734.80, both the Program Fee alone. A Monthly Summary workbook's Total Costs
  also counts spot and usage mail and points in months they occur.

**A total column now comes before its last-month figure** ("always show the big number
first"):
- **ARS:** Revenue PTD and Profit PTD come before the current month's incremental revenue.
- **ICS:** PTD and YTD come before last month, its goal and % of goal, and the YTD tile
  leads the last-month tile.
- **MRPC:** trailing-12 enrollments come before last month's.
- **Already total-first:** CashPlease and the Client overview.

### 2026-09-14 — trend lines on the performance page show complete months only

**The ICS, MRPC and CashPlease sparklines no longer end on a month in progress** (Aaron:
"on the trend line for ICS, MRPC and CashPlease don't include incomplete months"). A trend
that ends on a partial month reads as a fall-off. In 2026.09, nine ICS trends ended on 13
days of September.

- **ICS.** The VIP trend's month-to-date point, which VIP flags `partial_last`, is dropped
  from the referrals, goal and months series (`complete_trend`). The column header now reads
  "Referrals by month", because the trend is no longer a fixed 15 months.
- **MRPC and CashPlease.** A month on or after the month the weekly report was generated is
  dropped (`complete_months`). The 2026-09-13 weeklies already ended in August, so today
  that removes nothing, but it stops a mid-month weekly from adding a partial month. MRPC's
  "last month" and "trailing 12" columns are read from the same series, so they count
  complete months too.

Year-to-date, program-to-date and CashPlease's trailing-12 loans still come from VIP and the
CashPlease extractor, unchanged.

### 2026-09-14 — every table on the performance page sorts by its columns

**The product sections' tables sort, as the Build readiness table already did** (Aaron: "i
want to be able to sort the product columns too, such as by loss rate"). This covers Client
overview, ARS, ICS, MRPC and CashPlease. Every column that carries a value has a sort
button; the sparkline trend columns do not.
- **Clicks.** A numeric column sorts highest first on the first click, so CashPlease's
  charge-off rate is one click. A text column sorts A to Z. The next click reverses, and the
  third clears the sort.
- **Scope.** Each section keeps its own sort, remembered per viewer.
- **Values.** Each cell is sorted by what it shows (`$1.6M`, `−$1.2M`, `6.85%`, `5.75 : 1`,
  `Aug 2026`), never by its sub-label.
- **Rows that don't move.** A client with no figures and the CashPlease all-clients peer row
  stay at the bottom in both directions.

### 2026-09-14 — a Client overview section on the performance page, from each ODD extract

**The page opens with a Client overview.** Aaron asked for "total open checking accounts,
total business, total personal, 3-month average swipes per month for personal, 3-month
average NSF/OD items per month, 12-month personal openings, 12-month personal closings".
It has a ranked bar of open checking accounts, one table row per client, and a summary tile.
The section is client-level, so it shows whatever products are selected.

**Every figure uses the decks' definitions**, read by `scripts/perf_overview.py` through
`build/ars_pipeline/odd_rows`:

| Figure | Definition |
| --- | --- |
| Open checking | Accounts whose status is not closed: the Product Mix slide's "Excl. Closed" book, so the totals match that slide. Business and personal come from `Business?`; a blank is neither and counts in the total only. |
| Personal swipes | Signature plus PIN counts on personal accounts over the extract's last three months, averaged. |
| NSF/OD | Item counts, never dollars, on every account over the same three months. |
| Openings and closings | Personal `Date Opened` / `Date Closed` in the twelve months ending with the extract's month: `metrics_gen`'s openings-vs-closures rule, over 12 months instead of 24. |

**Each row names the month its extract describes and is tagged when that is older than the
cycle's.** `Inputs/ODDD/<id>_ODDD.zip` has no period in its name, so last month's file looks
like this month's. For 2026.09 a current extract ends in Aug 2026.

Reading 83 extracts (3.9 GB) over the share is slow, so each result is cached in
`Build Artifacts/perf_dashboard/odd/<id>.json`, keyed on the zip's size and time. A refresh
reads only an extract that changed. A client with no extract (1002 Republic, 1095 Landmark
Bank) says so. Tests: `tests/test_perf_overview.py`, plus new cases in
`tests/test_refresh_performance_dashboard.py`.

**The open counts are checked against the Product Mix slide's own extractor.** Run on the
real 2026.09 extracts, `product_mix_slide.extract_product_mix` and the overview agree exactly
for 1204 (19,933 open: 3,403 business, 16,465 personal, 65 unmarked). They also agree for
1549 (31,949: 4,155 / 27,794 / 0), whose core leaves `Stat Desc` blank.
`test_open_counts_match_the_product_mix_slide` pins that agreement, so the two cannot drift.

The first pass read 78 extracts in 571 s. Seventy-seven end in Aug 2026. **1195 KEMBA CU's
extract ends in Apr 2026** even though it was filed as 2026.09, and the page tags its row.

### 2026-09-14 — filter chip colors: white for a whole row, blue for a pick, gray for off

**The filter chips' three states now read white, blue and light gray** (Aaron: "go white for
all selected, blue for individual selections, and add a slight gray for unselected
options"). This replaces the green, blue and white set from earlier the same day.

| State | Chip |
| --- | --- |
| Whole row selected | White, hairline border |
| Selected | Blue `#245C8C` |
| Not selected | Light gray `#E9EDF1` |

Unselected filter chips have their own `--chip-off` tokens, so the white input chips in the
Build readiness table are unchanged. The dark theme has the same three steps, and the key
under the filters follows the tokens.

### 2026-09-14 — client marks removed from the performance page

**The per-client marks on the ranked bars are gone** (Aaron: "remove the favicon idea. Not
enough clients have them."). A mark could be cut from their own logo for only 20 of the 85
clients. The other 65 showed initials, and 58 of those would each have needed a hand-made
square mark.

Removed: `scripts/perf_marks.py`, its tests, the dataset's `marks` key, and the page's mark
tiles. The bars render as they did before the marks. The three-state filter chips and the
empty-selection filters stay, and so does the duplicate top-level name test, which guards the
page script rather than the marks. The marks cache in `Build Artifacts/perf_dashboard/marks/`
is no longer read.

### 2026-09-14 — client marks on the performance page's bars, and filter chips that show their state

**Each name on the four ranked bar charts has the client's mark beside it** (Aaron picked
concept A from four drawn on the real ARS bars). Client logos are wordmarks far more often
than square icons, so `scripts/perf_marks.py` chooses a mark in this order:
1. A curated `Inputs/Logos/<id>_mark.png`, which always wins.
2. The icon leading the logo, when a clear gap sets it apart from the wordmark.
3. The whole logo, when it is no wider than 1.6:1.
4. Otherwise, the client's initials.

A pure wordmark is never cropped, because a crop of its left edge cuts a letter in half.
The marks are part of the dataset, so a new or curated logo moves the hash and republishes
the page. They are cached by logo file size and time in
`Build Artifacts/perf_dashboard/marks/`. The first run over 85 clients took about three
minutes.

On 2026-09-14 the result was 11 icons, 9 whole logos and 65 monograms. 58 of those 65 have
a logo on file, and each refresh lists them by id: they need a curated square mark.

**The filter chips show three states** (Aaron: "use a 3rd color for when all of a row is
selected, blue for on, white for off"):
- Green (`#E3F1EA`): the whole row is selected.
- Blue (`#245C8C`): selected.
- White: not selected.

Before, a whole-row selection left every chip unmarked, so "all" and "none" looked the same.
Each row now leads with an All chip, which replaces the "All CSMs / products / clients" links
at the right, and a key under the filters names the three colors. Green was picked because
the product chips already carry the program colors. Tests: `tests/test_perf_marks.py`, plus
new template cases in `tests/test_refresh_performance_dashboard.py`.

**A top-level name declared twice in the page's script now fails the suite.** The marks
were first added as `const MARKS` beside Mark sent's `let MARKS`. That is a SyntaxError,
and the page rendered only its filter rows, while every string check in the tests still
passed. The preview caught it before it was published.
`test_template_declares_no_top_level_name_twice` reads the script's column-0
declarations.

### 2026-09-14 — the performance page's filters allow an empty selection

**Any chip can be clicked off, including the last one in its row** (Aaron: "allow zero
selection for CSM, client, etc at the top"). The CSM, product and client rows each used to
keep at least one chip selected. With a row empty, the page says which filter is empty and
points to its All link, instead of showing a blank page. An empty selection is saved as
empty and survives a reload, while "all" is still saved as all.

The page used to reset an empty client selection to all on every render. That reset was
meant for a stale saved selection, so it now runs once, on load, and only when saved
clients match none of the saved CSMs. `tests/test_refresh_performance_dashboard.py` pins
all three rows and the reload.

### 2026-09-14 — the performance page lists every current client and links the workflow

**The page shows all current clients across the five CSMs** (Aaron: "i want the artifact
to show ALL current clients, and then be able to filter by CSM"). It lists the
`clients.md` roster plus every client with reports filed on `Velocity_clientreports` for
the newest month at or before the cycle, except the clients `clients.md` marks as stopped.
1437 Canandaigua is one of those and still lands reports. `scripts/perf_clients.py` reads
the share, and its last answer is kept in `Build Artifacts/perf_dashboard/current.json` for
mornings off the VPN.

**Programs for a client `clients.md` does not list are inferred from that month's files**
(Aaron chose this over recording all 81 current clients in `clients.md`):

| File on hand | Program |
| --- | --- |
| ARS workbook on the share | ARS |
| VIP ICS sheet | ICS |
| MRPCPM analysis, or a tab in the MRPC weekly | MRPC |
| Tab in the CashPlease weekly | CP |

A DCO alone implies nothing. The page tags those clients "from data" and lists a client
with no program data this month under all products. The ARS format (Lift Matrix or Monthly
Summary) is read off the workbook, the same test that set `clients.md`'s Path column. This
is for reading only: `clients.md` still decides what gets built. On 2026-09-14 only 1 of
the 35 non-roster ARS workbooks on the share had been copied to `Inputs`, so the rest show
"not yet copied" until the daily copy picks them up.

**A click on a product chip now shows only that product**, the same as the CSM and client
chips. It used to remove the clicked product from the selection.

**A saved filter of "all" now stays "all".** The page remembered each filter as the exact
list selected, so "all" was saved as that day's 20 clients. The first all-clients build
therefore opened on Aaron's 20 and hid the other 65. "All" is now saved as all, under a new
storage key, so selections saved the old way are ignored.

**The page links a workflow page**, `scripts/perf_workflow.html`, published as
`workflow.html` in the same artifact. It covers:
- the cycle from files landing to a deck recorded as sent
- each program's inputs, and what happens when one is missing
- where everything lives
- what stops a deck
- the filename convention

The daily refresh republishes only the main page, so a change to the workflow page has to
be published by hand. Tests: `tests/test_perf_clients.py`, plus new cases in
`tests/test_refresh_performance_dashboard.py`.

### 2026-09-14 — the archive keeps one deck per period and kind, in a folder per client

**`Outputs/Archive/` had become a flat pile of every rebuild.** 97 files for 15 clients,
nine copies of 1038's September ARS deck among them — each rebuild during the month
archived the one before (Aaron: "in the archive, only keep the last deck created for each
individual period per client, and organize them into folders per client").

- **A folder per client.** `promote_month` archives a superseded deck to
  `Archive/<id> <client>/`. The id is the key: an existing folder for that id is reused
  whatever its name, because delivery names differ by program ("Marine FCU" on the
  Executive Review, "Marine Federal Credit Union" on the CashPlease module).
- **The newest deck of each kind per period is kept** — kind being the program tags, so a
  client's September CP module and its September ICS-CP deck both survive (Aaron's choice
  over one deck per period). Newest is the deck's own build time.
- **Older ones are moved, never deleted**, to
  `Archive/_older decks - delete after review/<id> <client>/`. The share has no Recycle
  Bin, so emptying that folder is a person's decision. The tidy runs only after a
  successful delivery, so it can never cost one.
- **PDFs never move** — they are exported by hand before sending.
- A failed promotion still leaves Outputs as it found it, and now also removes a client
  folder it had just created.

The existing archive was reorganised the same way, through the same functions.
`tests/test_promote_month.py` pins the name parsing, the client folder, folder reuse,
the keep rule with PDFs left alone, and the tidy after delivery.

### 2026-09-14 — the pipeline root moved to the CSM_Reporting share

**`RPE_DATA_ROOT` is `\\PADMIS105\Velocity_company\CSM_Reporting`** (Aaron: "we have a new
folder for imports, exports, and other project files … repoint everything"). With the ODD,
DCO and workbook copy now covering all five CSMs' books, a root on one laptop was the wrong
home for it. No code path changed: every reader already resolves through `rpe_env`, so the
move was a copy and one `.env` line — the reason the path was never hardcoded.

- **Copied, then proven, then switched.** A full robocopy (1,926 files, 2.365 GB, 0
  failures), a SHA-256 comparison of every file, and a catch-up pass for the files other
  sessions wrote during the copy (247 more, 0 failures) — ICS Charts workbooks re-saved at
  15:38, 67 CSM client logos, and the 16:00 performance-page rebuild including its
  `published_hash`, so the 08:30 refresh does not republish an unchanged page. Nothing on
  either side was deleted.
- **The old local root is retired, not deleted.** `C:\Data Pipelines\RPE Pipeline` was
  renamed to `C:\Data Pipelines\RPE Pipeline (retired 2026-09-14 - use CSM_Reporting)`
  after verification (all 2,050 files intact), so nothing can keep writing to a copy
  nobody reads; the share is the one copy.
- **The share needs the VPN off-site**, the same as the source shares it copies from.
- `.env.example`, the example path in `rpe_env`'s "RPE_DATA_ROOT is not set" message, and
  CLAUDE.md **File locations** name the share.

### 2026-09-14 — the ODD copy pulls from all five CSMs' folders

**The daily watch only ever looked in Aaron's ODD folder.** The data team lands each
CSM's extracts in that CSM's own folder on `Velocity_company`, so the 08:00 copy and the
delivery dashboard's "has it landed" check saw one book out of five (Aaron: "update the
ODD copy to pull from all 5 CSM folders"). `deck_status.SRC_ODDD` now lists all five as
`CSM=path` entries — Aaron Burgard, Daniel Wood, Gregg Miller, James Gilmore, Jordan
Berkowitz — overridable with `RPE_SRC_ODDD` in the same format; a bare path still works.

- **Five naming conventions for one month.** `2026.09 Sep` (Aaron), `2026.09` (James),
  `September, 2026` (Jordan, Gregg), `090126` (Dan, the first of the month).
  `deck_status.odd_folder_period` reads all four and nothing else, so `Archive`, `2025`
  or a folder named after a client's core migration is skipped rather than guessed at.
  The old code globbed `<period>*`, which matched only Aaron's naming.
- **Every client's files, not only the roster's.** `copy_plan(..., stopped=...)` copies
  ODD extracts, DCOs, ARS workbooks, MRPCPM analyses and ICS workbooks for any client on
  the shares — every CSM's book (Aaron: "update the DCO and workbook copy to pull all
  clients too") — except the clients `clients.md` marks as stopped (1437, 1174, 1658
  today). The reports share was already scanned across all five account-manager folders;
  only the roster filter kept the other books out. With `clients.md` unreadable the
  stopped set is unknown and the copy falls back to the roster rule, which copies nothing
  rather than everything.
- **A client in two folders.** Same client and month in two CSM folders (a handover —
  1808 Summit Choice sits in both James's and Jordan's) takes the more recent write.
- **One unreachable folder is off VPN.** The run exits 2 and saves nothing, and the
  report names which folder failed. Scanning the four that answered would have reported
  every extract in the fifth as gone.
- The report tags each ODD line with the CSM folder it came from.

The first run after this lists the other four CSMs' extracts as new once; that is the
inventory catching up, not a landing. `tests/test_watch_sources.py` pins the four
namings, the named/bare root parsing, the tagged scan, the unreachable-folder rule, the
stopped-client exclusion and the tie-break; `tests/test_deck_status.py` follows the
month-folder lookup.

### 2026-09-14 — filter the performance page by CSM

**The RPE Client Performance page has a CSM filter at the top** (Aaron: "the RPE artifact
is going to need the ability to filter by CSM at the top"), above Products and Clients.
It uses the same chips: from "All CSMs" a click isolates one CSM, later clicks add or
remove, and shift-click isolates. The Clients row then offers only that CSM's clients,
the summary tiles and every section follow, and the choice is remembered per viewer.
Changing CSM resets the client selection, so a client picked under one CSM cannot leave
another CSM's view empty.

**Where the CSM comes from.** The data team files every client's reports under
`Velocity_clientreports\<period>\<Account Manager>\`, so the refresh reads that folder as
the client's CSM. It uses the newest of the last two months at or before the cycle: a
client moved between CSMs follows the move (1805 went from Matt Lindsey in 2026.08 to
Jordan Berkowitz in 2026.09), and a client whose files have not landed yet keeps last
month's CSM. The share needs the VPN, so the last answer read is kept in
`Build Artifacts/perf_dashboard/csm.json`. Without it, a morning off the VPN would blank
every CSM, move the content hash and republish.

**When the share names nobody**, the refresh uses the new `CSM` column of the CashPlease
roster in `clients.md`, then the CSM on the client's CashPlease settings record. The column
exists for the five CashPlease-only clients (1131, 1564, 1750, 1770, 1771): their reports
never land on the share and none has a settings record, so the first build showed them as
Unassigned. If the share and the column disagree, the share wins and the refresh logs the
disagreement, because the share is kept by the people who assign clients. **A client
nothing names is shown as Unassigned, never given a default CSM**: a guessed CSM hides the
client from the CSM who actually owns it. As of 2026.09 every roster client resolves to
Aaron Burgard.

The refresh now reads the roster through `build_month.read_cashplease_roster` (columns by
header name) instead of its own parser. That parser took Build from the third cell, so
the new column would have dropped every CashPlease client from the page. Who appears on
the page is still decided by `clients.md`, so it shows only Aaron's clients; other CSMs'
clients appear only if they are added there.

### 2026-09-14 — undo a recorded send from the performance page, with a confirming click

**A recorded send can now be undone on the page** (Aaron: "click the Sent button to undo
the recorded date, add a click to confirm"). The sent date in the Build readiness table is a
button: one click turns it into "Undo send?", a second click within five seconds removes
the record, and a click elsewhere or Esc keeps it. The old "undo" link only reached sends
recorded on the page and not yet folded into `deliveries.json`; a send already in the log
showed as plain text and could not be undone at all.

**An undo is a row, never a deletion.** The page cannot change `deliveries.json`, and a send
recorded on the page may already have been folded in by the time someone undoes it — so
deleting the page's row would have left the log's copy standing and the date would come back
at the next refresh. The page now writes `{"unsent": true, "undo_of": "<date>"}`, and Mark
sent after an undo writes a send row carrying `undo_of` too. `merge_sent` applies either one
only while `deliveries.json` still holds exactly that date: an undo removes the entry, a send
replaces it, and a row naming any other date is reported as stale and left alone, so an
older undo can never erase a send recorded after it. "deliveries.json wins" still holds for
every plain row. The page reads its own rows by the same rule, so it shows the result
before the refresh does. `tests/test_refresh_performance_dashboard.py` pins removal,
replacement, the stale cases and malformed undo rows; the `rpe-dashboard-refresh` task
instructions describe the exception.

### 2026-09-14 — the Mailing Response Summary lists a mailing still in progress

**A mailing whose response is not yet measured was on no slide.** 1549 Wellworth's
September deck showed "The program's first mailing" — Jun 2026 — while its ODD extract
(Mar26–Aug26) also carries an Aug 2026 mailing on 9,643 accounts with `Aug26 Resp`
blank for every one. `metrics_gen` keeps only "mature" mailings (those with a following
month of activity), which is right for every rate, and dropped the rest without a word.
The workbook does not list it either: its Mail Response Summary MM ("August 2026 Data")
carries Jun 2026 only (Aaron: "if the client has a mailing in process but incomplete,
list it here").

`metrics_gen` now emits `mail_in_progress` — each mailing with no following month and at
least one offer, counted the way the completed rows count (personal accounts carrying a
`<Mon> Mail` value). The builder lists it first as "<Mon YYYY> (in progress)" with the
offers sent and "Pending" in every response column — never a blank or 0.0%, which would
read as a drop that drew nobody. It never enters a rate or the trailing total. The
subtitle names it ("The program's first completed mailing; Aug 2026 still in progress.")
and the notes say why the figures are pending. The label does not match "Mon YYYY", so
`mailing_table_findings` still compares only completed mailings with the count the deck
states. When twelve completed mailings, the total and an in-progress row exceed the
template's 14 rows, rows are added and the table held to the template rows' 5.60in, so
it ends at 7.10in exactly as the delivered 12-mailing decks do (checked in a PowerPoint
render of 1204: fifteen rows, total last, nothing clipped).

**It also lists a mailing dated AFTER the extract's last month.** Five extracts ending
Aug26 already carry populated `Sep26 Mail` offers with no response (1204, 1509, 1537,
1539, 1676), and by the same rule those read "Sep 2026 (in progress)". Of the delivered
2026.09 decks, eight would change: 1038, 1549, 1705 (Aug 2026) and those five (Sep 2026).
Only 1549 has been rebuilt (staged; gate PASS, slide 13 the only difference).

`tests/test_metrics_gen.py` adds a mailing to the synthetic ODD's last month and asserts
it is listed as in progress with the completed rows and total unchanged.

### 2026-09-14 — CashPlease Program Settings in the review, and pills that wrap

**The CashPlease section gains a Program Settings slide** for a client whose production
settings are on file (Aaron: "add those to the CashPlease section of the RPE review").
The record is the client's row on the CashPlease page of the Velocity Product Settings
Power BI app, first pulled for 1632 WesBanco on 2026-09-14 for their ops meeting. It now
lives at `Inputs/Product Settings/<id>_cp_settings.json` (a copy of
`C:\Data Pipelines\Product Settings\Inputs\1632 WesBanco\wesbanco_cp_settings.json`),
resolved by `rpe_env.cp_settings_file` — never read from the other project's tree.
`build_cashplease.py` passes it to `build_cp_gen.py`, which places the slide after the
Program Overview: loan terms beside eligibility and controls, and a program strip. The
module goes from ten slides to eleven and the combined section from five to six.

- **Production values only.** The ops deck's orange recommendations (a 120-day waiting
  period, a $150 first loan) are agenda items for that meeting, not settings, and are
  not on this slide.
- **Internal fields never reach the file.** The record carries Loan Notes ("Declined
  Best Practices…"), contract type, core, CSM, pricing and the regulator address.
  Speaker notes ship inside the `.pptx`, so the builder reads only the fields named in
  `SETTINGS_SHOWN`; a field added to the app later is ignored by construction.
  `tests/test_cp_settings_slide.py` plants sentinel values in every internal field and
  fails if any reaches the slide or its notes.
- **A record for another client or program is refused** (`Customer #`, `Record Type`),
  and so is one with no `_source`, since the slide's source note is built from it.
- **No record, no slide.** Seven of the eight CashPlease clients have no settings file
  yet. A slide of "Not recorded" would say nothing, so they keep the five-slide section
  and `build_cashplease.py` lists them by name at the end of every run.
- `Product Settings/` is excluded from `report_dirs()` and the watch's copy/prune scan
  (`rpe_env.NOT_SCANNED_KINDS`), like `ODDD/`: it is resolved by exact path.

**Every September CashPlease and ICS date pill wraps to two lines, and nothing said so.**
The settings slide's first pill, "As of September 14, 2026", rendered on two lines in
PowerPoint. The validator missed it because the pill box holds two lines and nothing
sits beneath it, and `single_line_overflow_findings` only fails a spill onto other text.
Worse, PowerPoint wraps before the measured text reaches the box: twelve pills rendered
through PowerPoint held one line at up to 0.940 of the usable width and took two from
0.974 — the settings pill was 0.993, "PTD · September 4, 2026" is 0.984.
`pill_wrap_findings` now REPORTS any pill past 0.955 (`PILL_WRAP_RATIO`). It is REVIEW,
not FAIL, because the fix is a cross-program style decision (a shorter date or a wider
pill) and is not made here. The settings pill uses the short month ("As of Sep 14, 2026").

### 2026-09-14 — the first four-program deck: a cover that overflowed, and a client with two names

Marine FCU's September deck is the first combined Executive Review with all four programs
(ARS-ICS-MRPC-CP), assembled alongside ICS-CP decks for 1632 WesBanco and 1734 Altamaha
(Aaron). WesBanco and Altamaha passed the gate; Marine failed it three times, on two
defects no earlier combined deck could reach.

**The cover listed four products in a box that seats three.** `set_title_products` adds a
paragraph per program at the shell's 40pt, and the product box is 2.0" deep — exactly three
lines. Four ran about 2.7" deep and drew over "Marine FCU / Executive Review" beneath them.
`_fit_product_lines` now shrinks the product lines only when they cannot fit at their own
size, so two- and three-product covers keep exactly 40pt and no existing deck changes.

**The leak checks treated one client's two names as two clients.** Marine FCU (1539) is the
old reference client, so both "Marine FCU" and "Marine Federal Credit Union" are on
`validate_deck.REFERENCE_CLIENTS`. A name is skipped only when it appears on the deck's own
filename or cover — and the cover says "Marine FCU" while the CashPlease workbook, and so
the CashPlease section's source notes, say "Marine Federal Credit Union". Slides 42 and 46
failed as "a different client's provenance". `REFERENCE_ALIASES` now groups the two names,
and both `reference_leak_findings` and `source_note_findings` count a name as the deck's own
when any name in its group is. A genuinely different client still fails.

`tests/test_combined_cover_and_names.py` pins both: four products fit, two and three keep
40pt, the alias works in both directions, and True Sky's deck naming Marine is still a leak.

### 2026-09-14 — the Build readiness table sorts by every column

Every column on the performance page's Build readiness section is now sortable (Aaron):
click a header for ascending, again for descending, a third time to clear back to client
id order. The choice is remembered per viewer in `localStorage`; a stored value the page
does not recognise is ignored. Headers are buttons inside the `th`, so they work from the
keyboard and carry `aria-sort`, and focus returns to the clicked header after re-render.

Each column sorts on what it means, not on its markup: **Ready** puts ready before blocked;
**Inputs** orders by missing, then stale, then unconfirmed inputs; **Deck** puts this
period's build first; **Sent** puts decks still to send before sent ones. A row the column
does not apply to — no readiness check (the CashPlease-only clients), or no deck to send —
stays at the bottom in both directions, so flipping a sort never floods the top with blanks.
Ties fall back to client name in a fixed direction so equal rows do not reshuffle.

**Caught in testing:** Deck first treated "no deck" as not-applicable. Every built deck
ties, so the unbuilt rows sat at the bottom both ways and descending rendered exactly like
ascending — the click looked broken. No deck is the state that column exists to show, so it
is now the last rank and descending puts it first.

### 2026-09-11 — revenue under $1M reads in K, and promote_month stops being a trap

**Five copies of the money rule, and they disagreed** (Aaron: "when revenue is less than
$1M, state it in K"). The ICS Present Value callout divided by a million unconditionally
and printed **$0.83M** for $830K; `ics_charts_gen`'s donut centre fell back to a full
`$830,000`; `build_ars_gen` carried both an unconditional `m2()` and a correct `_fmtk` two
hundred lines apart; `build_mrpc_gen` wrote life-of-program in M whatever its size. All
now call `brand.usd_compact` — `$1.24M` at a million and up, `$830K` below, and the whole
figure under a thousand because "$1K" for $950 is worse than the characters it saves.
MRPC's "$95.6K in 2025" keeps its decimal: it already states K, and the rule is about the
unit, not the precision.

**The fifth copy was in the VALIDATOR, and it failed a correct deck.** `extract_findings`
formatted the EXPECTED `ltd_profit` with its own `/1e6:.2f}M` and looked for it verbatim
in the deck. The moment the builders started writing $830K the cross-check went hunting
for "$0.83M" and the golden deck went red. An expected value formatted differently from
the rendered one is not a check. `tests/test_brand.py` now scans all five files — code
only, since it was flagging its own explanatory comment.

**promote_month: two failures and the trap underneath them.**

A deck open in PowerPoint raised PermissionError, **aborted the whole run at the first
client**, and left that client's hand-made PDF in `Archive/` while its superseded deck
stayed live. Promotion is now all-or-nothing per client — anything already moved is put
back, and the orphan `shutil.move` leaves behind when it falls back to copy-then-delete is
removed — and a blocked client is REPORTED while the run continues, with the exit code
carrying it.

Underneath both: **`main()` resolved its destination from `rpe_env.outputs()` and ignored
its caller.** A test that built a temp `Outputs/` and passed the staging dir to `main()`
wrote into the LIVE folder and delivered 1204's deck under 1038's filename. Recovered from
`Outputs/Archive/` and rebuilt; nothing was sent, and an audit of every delivered 2026.09
deck's title-slide client against its filename found no other mismatch. The destination is
a `--outputs` parameter now, and `tests/test_promote_month.py` re-runs that exact scenario
and asserts the real folder is untouched.

That is three defects in one module from the same root: it reached for globals instead of
taking parameters. Import-safe, parameterised, and covered now.

**PDFs in `Outputs/` are deliberate** (Aaron, 2026-09-11): they are exported by hand before
sending, so they are not strays to clean up. `promote_month` archiving them alongside the
deck is correct — a PDF of a superseded deck is stale — and that move is now part of the
same all-or-nothing group.

### 2026-09-11 — promote_month could not see a colour change, and skipped the delivery

**The navy Summit banner was silently not delivered.** True Sky was rebuilt with the
recoloured banner, passed the gate at 0 FAIL, and `promote_month` reported it
`unchanged` and left the old deck in `Outputs/`. `same()` compared slide TEXT and IMAGE
blobs only — a shape's FILL is neither, so a rebuild whose only change is a colour was
indistinguishable from no rebuild at all. A check that cannot see the change reports
success, which is the failure mode this pipeline keeps paying for.

`same()` now also compares how the shapes LOOK: kind, box, solid fill and line colour,
per shape per slide. All of it is derived from shape properties, so it stays stable
across rebuilds the way zip bytes are not — and zip bytes are still deliberately NOT
compared, because they differ on every build and comparing them would re-archive an
unchanged deck every run, which is the thing `same()` exists to prevent.

Verified three ways before delivering: navy vs delivered -> False (the change is seen),
each deck against itself -> True (no false positives).

### 2026-09-11 — the ODD accessors, measured: metrics_gen ~10%, and where the time really is

`odd_rows` accessors run tens of millions of times per client, so the obvious per-row
waste was removed: `mkey` memoised (185,000 `strptime` calls for about three dozen
distinct month tokens), the constant columns (`Business?`, `Debit?`, `Stat Desc`) bound
once instead of hashed per row, the per-month column indices cached so `swipes`/`spend`/
`nsf` stop building `"Jul26 Sig #"` on every call, and `fnum` trying `float()` on the raw
cell first — it already tolerates whitespace and raises on exactly the inputs the
strip/replace path exists for.

**Measured, not assumed.** `metrics_gen` 9179 -> 8262ms on 1676 and 16424 -> 15892ms on
1539 (means of 2-3 runs): 3-10%. **`oddd_optimize` did not change at all** — it has its
own classifiers and barely touches the shared accessors. Every metric is byte-identical:
the `metrics.json` for 1038, 1204, 1676 and 1539 match their pre-change SHA-256 exactly.

**A hypothesis that measured worse, and was removed.** `resp()`/`mail()` accessors were
added to kill the `g(r, f"{m} Resp")` f-string in the hottest loop — 28 call sites. They
made it SLOWER: one call plus a string build became two calls, and 1676 went 8882ms with
them to 8262ms without. Reverted.

**Where the build time actually is** (1676, ~70s): `build_ars_gen` 18.8s, `charts_gen`
11.7s, `oddd_optimize` 10.0s, `metrics_gen` 8.9s, the rest in the extractors, the ICS
build and assembly. The ODD stages are 27% of the build and the largest single stage
touches no ODD row, so this whole change is worth about 1% end to end. Profile the chain
before optimising a stage of it.

**The one structural ODD lever left, NOT taken.** Building the retained row store costs
~3.0s and reloading the same store costs 0.35s, and three processes each build it
independently — about 5s per ARS client. If that cache is ever built it must be
CONTENT-ADDRESSED, keyed on a hash of the zip (~0.2s for 49 MB) and never on path+mtime:
a cache that can go stale manufactures precisely the stale-ODD failure this pipeline has
shipped before, where the wrong month validates perfectly because it is internally
consistent.

`tests/test_odd_rows.py` gains 58 equivalence cases pinning every optimised accessor
against a literal transcription of the original — 24 cell shapes against every column,
the month helpers, the flags, short rows, empty rows and an empty header map. This is the
vocabulary that drifted across three implementations once; "it still runs" is not the bar.

### 2026-09-11 — build-order audit: a duplicate pass, a stale deck picker, and the Summit gap

**ARS decks were restyled twice.** `build_ars_gen` runs `restyle_fonts` and then its
branding, geometry and layout-fit passes before saving; `build_month` ran `restyle_fonts`
AGAIN on the finished file. Measured on a delivered 49-slide deck the second pass changed
nothing on any slide — a subprocess and a full load/save per ARS client for a no-op — and
it re-applied font roles after `fit_layout` had clamped them. ICS and MRPC never had it,
so ARS was the odd one out. Removed.

**`promote_month` could not pick a CashPlease combined deck.** Its combined-deck test was
three literals — `("ARS-ICS", "ARS-MRPC", "ICS-MRPC")` — written before CashPlease became
the fourth program. An `ICS-CP` deck matched none of them and fell through to the "most
slides wins" tiebreak, which picked the right file for 1632 and 1734 by luck rather than
by rule. `program_tags()` now derives them from the filename convention, and a combined
deck with MORE programs wins, so `ARS-ICS-MRPC-CP` beats `ARS-ICS` when both are staged.

**...and could not be imported, which is why that went unnoticed.** It read `sys.argv[1]`
at module scope and did the whole job there, so importing it RAN it — the hazard CLAUDE.md
names for `metrics_gen`. Nothing could import the module to test `deliverable()`, so the
stale tag list had no test to fail. Restructured behind `main()`.
`tests/test_entry_points.py` now pins the class rather than the instance across all eight
drivers: resolve siblings from `__file__` and never the home directory, no `sys.argv` at
module scope, and a `__main__` guard.

**QA gap — nothing failed a deck advertising a Summit that had already happened.** All
eighteen delivered 2026.09 decks named a Summit eleven days gone.
`summit_slide.summit_period()` warned on stderr, but only when a build called it for a
reporting month, and a warning in a build log is not a gate.
`validate_deck.summit_date_findings` reads the slide in every deck. It is **REVIEW, not
FAIL, deliberately**: a deck built the day before an event is indistinguishable from one
built the day after it ended, and a rebuild of an older period must not be blocked.

**The template shells still carried the Boston slide.** `ars_template.pptx`,
`cashplease_template.pptx` and `multi-product_reference_deck.pptx` were stale on slide 2.
Built decks were correct — the builders replace it from the asset — but the shells are
what the gate validates, and the new rule caught all three. Refreshed through
`insert_summit_after_title`, the same one source the builders use. Baseline re-snapshotted.

**No checks were removed.** Counting findings per rule across eleven decks and templates,
13 of 17 produced zero — which is the PASSING state for a FAIL-level rule on a clean
corpus, not evidence of dead code. Deleting them would delete the checks that keep the
corpus clean.

**Known and NOT changed:** the ARS build streams the ODD three times — `oddd_optimize`
(10s), `metrics_gen` (9s) and `build_ars_gen` again, on True Sky's 49 MB extract out of a
70s build. Consolidating is a real refactor: these were re-implemented standalone once
before and drifted, which is why they now share `odd_rows.py`. It needs a decision, not a
drive-by.

### 2026-09-11 — the Summit slide's date banner is navy

The band behind "Fort Lauderdale, FL · November 4-5, 2026" arrived a medium blue that is
not in the palette (Aaron). It is now `brand.NAVY` (#00274C), read from `build/brand.py`
rather than typed in, so it moves if the palette does. Both runs on it keep their colours
and stay legible: the venue is orange, the date is BACKGROUND_1 (white).

Only the fill changed — no geometry, no text. **Decks were NOT rebuilt** (Aaron: "on the
next run"), so the eighteen delivered 2026.09 decks still carry the blue band and the next
rebuild picks this up.

### 2026-09-11 — the LibreOffice render check is gone; the package check absorbs what it can

**Removed, deliberately** (Aaron): LibreOffice is not going on the build machine, so
`qa_all.py`'s render smoke test — open each deck, convert to PDF, compare the page count
to the slide count — had never once run there. Every gate closed with a banner saying the
one check that proves a deck OPENS had been skipped. A check that cannot run is not a
check; it is a banner. Gone with it: `_find_soffice`, `render_check`, `--no-render` and
both skip banners.

**What it covered that nothing covers now.** Steps 1 and 2 read the deck THROUGH
python-pptx, which cannot see a malformed package — not hypothetical: seven 2026.08 ICS
decks passed at 0 FAIL while being unopenable. So the recoverable half moved into
`validate_deck.package_findings`, which reads the ZIP directly and needs no renderer:

- **any part name written twice.** Exactly the defect produced the same day by cloning the
  Summit slide — relating the asset's image Part carried its partname along, so a deck
  that already held `/ppt/media/image2.png` got the entry twice. The existing checks could
  not see it: they look at SLIDE parts, and these are media.
- **a CRC check on every member**, catching a truncated or corrupt part.

What is NOT recovered is everything past "structurally sound": a deck that opens but
renders wrong, a font that does not resolve, an image that will not decode. CLAUDE.md says
so rather than implying the gate still proves a deck opens, and says to open one deck
before a batch goes to clients.

**The new test found a bug in the new check.** `testzip()` RETURNS the first bad name on a
CRC mismatch but RAISES when a stream will not decompress at all, so a badly corrupted deck
threw `zlib.error` out of the gate — which reads as a broken validator, not a broken deck.
Caught and reported as a FAIL now. `tests/test_validate_deck.py` covers a sound package, a
duplicated part and a corrupt member.

All 18 delivered 2026.09 decks were re-checked against the stricter rules: 0 findings.

### 2026-09-11 — one Summit slide, from one file: Fort Lauderdale replaces Boston

**Every 2026.09 deck advertised a Summit that had already happened.** The slide read
"Boston, MA — August 31-September 1, 2026"; the next Summit is Fort Lauderdale,
November 4-5, 2026. Fourteen of the eighteen delivered decks carried it as text and the
other four as a picture.

**It was in two forms, and neither could be replaced from the pipeline.** ICS and MRPC
decks got `assets/Velocity Executive Summit.jpg` — a flat PICTURE of the slide — while
ARS and CashPlease carried the real one baked into their template shells. So replacing
the Summit meant editing three template shells AND re-exporting a JPG, which needs
PowerPoint or LibreOffice and therefore could not be done from here at all.
`insert_summit_after_title` now clones `build/assets/summit_slide.pptx` into every deck,
and the ARS and CashPlease builders call it like ICS and MRPC always did. That file is
also the one `summit_date()` reads, so the slide on the page and the date the build
derives cannot disagree. Replacing the Summit is now one file.

**The asset had never been committed.** `build/assets/summit_slide.pptx` has no history
before today: `summit_date()` returned None, `summit_period()` with it, and four tests
failed on the missing file. The Fort Lauderdale slide is the first committed copy.

**Cloning across decks corrupted the package until it was fixed.** Relating the asset's
image Part into a deck carries that Part's OWN partname with it, so a deck that already
had `/ppt/media/image2.png` wrote the entry twice — zipfile says "Duplicate name:" and
the result is malformed while every text and geometry rule passes, which is exactly how
the 2026.08 ICS decks shipped unopenable at 0 FAIL. Images are re-added from their bytes
through `get_or_add_image_part`, which assigns a free partname and dedupes by hash.
`tests/test_summit_insert.py` promotes that warning to an error and asserts no duplicate
zip entries, that no cloned picture has a dangling relationship, that the slide count does
not move when a Summit slide is already present, and that all four builders call the
shared insert.

The slide is replaced in PLACE when one is already there, never deleted and re-added —
freeing a partname is what hands a later slide the same number.

**The Summit slide had been exempt from the source-note rule by accident.** CLAUDE.md
requires a source line in every slide's notes; while this one was a flat picture it
carried no TEXT, so the validator's data-slide rule never reached it. The moment it
became the real slide, all six ICS-only and MRPC-only decks failed on a missing note.
The rule had always applied — the old shape hid it. `insert_summit_after_title` now
writes one note on every deck, DERIVED from the date line printed on the slide rather
than written as a constant, because a note naming last Summit's city is the stale caption
this pipeline keeps re-learning. The ARS shells' own line called it "standard ARS
Executive Review front matter", which stopped being true when every program began
cloning the same file.

`test_summit_period_reads_the_current_slide` pinned `2026.08` and now pins `2026.11`.
It is meant to fail when the asset changes: replacing the Summit should be a decision,
not a side effect.

### 2026-09-11 — the template shells had never had the geometry contract applied

**The Reg E rewording fixed the built decks and left the shells failing.** Rewording the
opt-in sentence to "have elected to extend their overdraft access to the debit card"
(2026-09-10) made it four lines in a box that holds three. `slide_geometry.py` was
rebalanced to give it the room, and every BUILT deck passed — the builders run that pass.
The shells in `templates/` do not, so `ars_template.pptx` and
`multi-product_reference_deck.pptx` sat at 1 FAIL each and the gate reported FAIL for
anyone who ran it. CLAUDE.md's rule is to fix the builder AND the template shell; only
half of that was done.

Both shells now have `slide_geometry.apply()` applied and saved, so they carry the same
geometry a built deck gets rather than a hand-measured approximation of it — one
definition, per that module's own docstring. What moved, on both Reg E slides (27 and 28)
of both shells: donut 2.85" -> 2.45", the three legend rows and their chips up by 0.38",
the caption to 5.35" and 1.10" -> 1.60" tall, the branch chart to 1.60" and 3.40" -> 4.50"
tall, its caption to 6.22". Plus a 0.02" nudge on "Who Responds — Balance Profile" from
the existing caption-below-chart rule. The ICS, MRPC and CashPlease shells moved nothing:
the contract is ARS-only, as its docstring says.

Slide 28 was fixed in passing — it carries the same box as 27 and the gate had not
flagged it, because the template's dummy sentence there happens to be shorter.

**promote_month.py could not run at all.** Its `sys.path` insert was
`os.path.expanduser("~/Projects/RetailPerformanceEngine/build")`, which is not where this
repo is — it sits at `C:\Projects` — so the script raised ModuleNotFoundError on import
and delivery had to be driven with a PYTHONPATH set by hand. It now resolves `build/`
relative to its own file, the way every other entry point does. A path written into code
is a path that is wrong on the next machine; that is the whole reason `rpe_env` exists.

### 2026-09-11 — the performance page lost every CashPlease figure, and gained a shareable export

**The CashPlease section was blank for all eight clients and nothing failed.** CashPlease
moved into this repo on 2026-09-10, and its build code was deleted from the standalone
checkout in the move. `refresh_performance_dashboard.py` still resolved the extractor as
`CASHPLEASE_HOME` or a sibling `CashPlease/build/cp_extract.py`, so it found nothing, and
the CashPlease block for every one of 1131, 1539, 1564, 1632, 1734, 1750, 1770 and 1771
reported missing. The run still exited `STATUS: changed`, which is what the scheduled task
publishes on — the next 08:30 would have put a page with a hole in it at the live URL.
The extractor is now resolved in-repo first (`build/cashplease_pipeline/cp_extract.py`),
with `CASHPLEASE_HOME` kept as a fallback for a pre-migration checkout. The same move had
left the DDA counts behind too: they are read from
`Build Artifacts/cashplease/dda_counts.json`, where `build_cashplease.py` writes them,
instead of through a `cp_env` import that no longer exists and whose failure was swallowed.

`tests/test_perf_dashboard_export.py` pins the extractor's resolved PATH, not merely that
one was found — asserting "not None" would have passed on the broken morning for anyone
with the old checkout still beside the repo. It also pins cp_extract's argument count,
since the refresh builds that command line by hand.

**`--export` writes a copy that can be handed to someone.** The published artifact is
wrapped in a document skeleton at publish time, so the template carries no
`<!doctype>`/`<head>`/`<body>` of its own and a saved copy opened from a file share has no
publisher to supply one. `--export [PATH]` emits the same rendered HTML inside that
skeleton — charset first, or the em dashes arrive as mojibake — with a `<title>` (the
template's lands in the body, where browsers ignore it) and a line on the page saying the
copy is a static snapshot of its period. The page's own pill says "Last updated", which
reads as something that keeps updating; a file passed around never will.

### 2026-09-10 — the YoY tiles were not year-over-year, and their captions named the wrong months

Cherry-picked from `claude/gallant-allen-dzs1zv` (`7a47b93`, written 2026-09-01 and never
merged), plus one more instance found on the slide beside it.

**The Items YoY figure was not a year.** `metrics_gen` searched the NSF series for the row
labelled `'Jun 25'` and compared it to the LAST row — so it was year-over-year only for a
June deck. On the 2026.09 decks delivered this week the last row is Aug 2026, making it a
**14-month change presented as year-over-year**:

| Client | Deck said | Aug'25 → Aug'26 |
| --- | --- | --- |
| 1038 Sugar River | −10% | **−1%** |
| 1204 FSB Michigan | −3% | **+1%** (wrong sign) |
| 1509 Texas Bay | +16% | **+13%** |
| 1676 True Sky | −22% | **−26%** |
| 1705 CoastLife | +13% | **+4%** |

And a client whose series began after Jun 2025 found no row at all and fell to an `else 0`
branch, shipping a **phantom 0%**. The comparison is now the same month a year earlier by
month arithmetic; absent, it yields None and the tile reads "n/a" with a warning rather
than a zero.

**Three tile captions were template literals.** `(Jun 25 → Jun 26)` uses two-digit years
and `NSF/OD (June)` carries no year, so neither the as-of caption pass nor the
stale-caption gate could see them, and every deck shipped the reference client's months.
All three now come from the data.

The third — **Spend YoY** on the Debit Card Swipes & Spend slide — was not in the
cherry-picked commit. Its FIGURE was already derived correctly; only its caption was
stale, so the tile read "(Jun 25 → Jun 26)" over a number comparing Aug 25 to Aug 26. Same
shape, one slide over.

**The Reg E vintage axis was a typed `range(2018, 2027)`.** An account opened outside it
counted toward the vintage pool and then vanished from the chart, so the chart and its own
pool disagreed. The axis is the years present in the data now.

Verified on 1038 and 1204: `nsf_yoy` −1 and +1 against a window of `['Aug 25','Aug 26']`,
all three captions reading Aug. 721 tests pass.

### 2026-09-10 — CashPlease is merged into this pipeline

The CashPlease build ran out of `C:\Projects\CashPlease` against this repo's shared style
layer. It now lives here, as the fourth program: `build/cashplease_pipeline/` and
`scripts/build_cashplease.py`, dispatched by the new `cashplease-deck` subagent.

**No ARS, ICS or MRPC behaviour changes.** The pieces this depended on had already landed
— `--cashplease` and the four-product agenda in `assemble_combined`, the text-over-text
rule in `validate_deck`, `templates/cashplease_template.pptx`, and the roster in
`clients.md`. What moved is the build itself.

**Paths resolve through `rpe_env`, and `CP_DATA_ROOT` is gone.** The workbook and the DDA
count come from `Inputs/Weekly Summaries/` via `report_files()`, decks go to `Outputs/`,
and packs and figures to `Build Artifacts/cashplease/`. The separate CashPlease pipeline
folder on Drive is no longer read: two roots for one pipeline is the two-stores problem
that deleted `build/{ics,mrpc}_pipeline/data/`.

**Three deletions, each because the thing it duplicated now exists here.** `cp_qa.py` —
its check is `validate_deck`'s text-over-text rule, and the port is better than the
original: glyph boxes on both axes, priced per paragraph. `cp_env.py` — `rpe_env` resolves
these paths. The mirrored `brand.TEAL` / `periods.mon_yy` fallbacks in `cp_charts.py` —
they existed because `da20266` was not on `main`, and it is now. A fallback that can never
fire is a second definition of the palette waiting to drift, which is what `brand.py`
exists to prevent.

**One roster parser.** `cp_roster.py` is folded into `build_month.read_cashplease_roster`,
beside `read_roster`. Two parsers over one `clients.md` diverge, and these two already
proved it: the CashPlease table sits between the ICS-only table and Status changes, and
`read_roster` classifies a row by the section above it, so every CashPlease client was
briefly read as an ICS client — 1658 Truliant included, which has no RPE program at all
and is the exact row `clients.md` exists to keep unbuilt. A test now holds that shut.

**CashPlease is WEEKLY**, the only program in the cadence table that is not monthly, and
it always builds from the most recent workbook rather than the one nearest a deck's
period. So a CashPlease section inside a monthly Executive Review can report a later date
than the sections beside it. That is intended and visible: `assemble_combined` prints
each section's period.

Built on the 2026-09-06 workbook with the 2026-09-10 DDA counts: eight 2026.09 decks,
1658 skipped with its reason, 0 FAIL. `tests/test_cashplease.py` adds 19 tests, each one
a defect that shipped or nearly did — the 30-character sheet-name cap, the trailing-window
rule, L8 never reaching a slide, a NULL DDA count never becoming a zero.

### 2026-09-11 — sent is recorded from the performance page, and one section can no longer blank it

Aaron asked to mark a deck sent by clicking the "not recorded" chip on the RPE Client
Performance artifact, with no date to type. That chip is now a **Mark sent** button
(`scripts/perf_dashboard_template.html`) that records today's date against the deck named
in the Deck column, keyed on that deck's period — the same `<client>|<period>` key
`deliveries.json` uses, not the cycle period, which differ early in a month.

The page cannot write to this machine, so a click writes a row to the artifact's own
store (the `db` capability, declared on the artifact) and the daily refresh folds it into
the log: `refresh_performance_dashboard.py --merge-sent <read_db export>` merges before
rebuilding, so the republished page shows a plain sent date. **deliveries.json stays the
one ledger** — an entry already there is never rewritten, so a date corrected by hand
survives a stale page row, and a malformed row is reported and skipped rather than
repaired by guessing. A wrong sent date is the failure that lets a client go unsent, and
a second ledger is the two-stores problem that shipped month-old ICS figures in August.
A client with no built deck has no button at all: sent is recorded, never inferred.
Recorded-from-the-page sends carry an `undo` until they are merged, because a misclick
otherwise had no way back.

Also here, found while testing the above: **one failing section took the whole page
down.** A build that could not read the CashPlease rollup left `cp_peer` null, the peer
row threw on it, and the throw blanked every section AND the roster over one missing
figure. The peer row now states its absence, and `update()` renders each section behind a
guard so a section that cannot render says so while the rest of the page stands.

### 2026-09-11 — a watchdog for the daily source watch, and a registration drift fixed

Three mornings running (2026-09-09, -10, -11) the unattended 08:00 fire of the "RPE
Source Watch" scheduled task produced nothing: no log entry, no report, killed by
Task Scheduler at its 30-minute limit. The process was not hung in our code — it was
created SUSPENDED and never executed a single instruction (0 handles, 0 CPU, one
thread parked in Wait/Suspended). Every run started by hand on an awake machine
finished normally in 1-3 minutes, including a manual retry today that also surfaced
every python launch in this pipeline appearing twice in the process list — the
second a direct child of the first, identical command line and creation timestamp —
consistent with (never positively confirmed) Symantec Endpoint Protection
intercepting process creation and relaunching under its own supervision. Because the
process never gets far enough into our code to run a timeout, the fix cannot be a
code-level one; it has to watch from outside.

`scripts/watch_task_watchdog.ps1` + `scripts/register_watchdog_task.ps1` add a
second scheduled task, "RPE Source Watch Watchdog", firing 15 minutes after the main
task. A healthy morning is a silent no-op (checked: `Report-IsFresh`). Otherwise it
finds any `watch_sources.py` process matching the suspended signature (near-zero CPU
and handles, old enough a healthy run would be done), kills the whole process tree,
and retries the main task — up to two cycles before logging for a human. Verified: a
real idle-but-running process (handles ~123) is correctly NOT flagged; the
stale-report-but-nothing-stuck branch correctly logs and exits for a human; the
healthy-and-fresh branch is a confirmed silent no-op, including through
`Start-ScheduledTask` end to end. The kill-and-retry branch itself is code-reviewed
but not fire-tested against a genuine suspended process — this environment's
sandboxing refused the `CREATE_SUSPENDED` process-creation call needed to manufacture
one, even for a `notepad.exe` control case.

Also fixed: `register_watch_task.ps1`'s checked-in `Argument` string had not been
updated when `--mail` was added to the live task on 2026-09-09 — re-running the
script would have silently dropped mail reading from a task that already had it.

**No client-facing figure moves.** The point is that a morning's inputs reach
`Inputs/` even when the unattended trigger is hit by whatever this is.


### 2026-09-10 — the Reg E slides are rebalanced, and the opt-in sentence reworded

**The branch chart was 3.40" tall and stopped at 5.35**, leaving roughly 1.4" of empty
slide under its caption while twelve bars and a rate line shared half the height the donut
column used. It is now **7.60 x 4.50**, running 1.60 to 6.10 alongside the left-hand stack,
with the caption following it down to 6.22. `charts_gen` DIM moved to 1520 x 900 to match
the box aspect, or the PNG would stretch.

Making the box taller made the chart WORSE at first: `chart_lib` sized the matplotlib
figure from its height (`H x aspect`), so a taller box produced a NARROWER figure — 5.40"
instead of 7.15" — with the same 10pt tick labels, and "3,825" met "2,434" under the bars.
The figure is now never rendered narrower than the box it lands in. The take-rate chart is
unaffected: identical figure at 8.20 x 3.20 before and after.

**"…are opted in to overdraft" became "…have elected to extend their overdraft access to
the debit card"** (Aaron, 2026-09-10) — the old phrasing reads as opting in to overdrafts
themselves, when the election is about extending existing access to the card. Changed in
both template shells and the builder swap.

That sentence needs FOUR lines at 16pt in the 3.75" left column and the box held three, so
**the gate failed the build** rather than letting it wrap into the page number. The donut
gives up 0.40" (2.85 -> 2.45), the legend moves up with it, and the sentence gets 1.60".
Nothing is shrunk below the 16pt floor.

Three positions that `build_ars_gen` and `slide_geometry` both set — the branch caption,
the legend rows and the summary sentence — now have **one owner**, `slide_geometry`. Two
owners for one stack is how a caption ends up floating in the middle of a taller chart.

All ten deliverable clients rebuilt at 0 FAIL and delivered; 12 Reg E charts verified at
the new height, 6 sentences verified reworded.

### 2026-09-10 — the daily source watch hung in Outlook two mornings running; it cannot now

The 08:00 "RPE Source Watch" runs of 2026-09-09 and 2026-09-10 were killed by the
scheduler at the 30-minute limit (Task Scheduler event 329), with nothing logged.
By hand the whole run takes about two minutes, mail step included. The hang is a COM
call into Outlook while it is starting up after login: `Dispatch` blocks with no
timeout and a thread cannot interrupt it. Meanwhile eleven files had landed on the
shares since 2026-09-08, six of them for roster clients, and none had been copied —
the share check had finished in under a minute both mornings and died unwritten.

Three changes in `scripts/watch_sources.py` and `scripts/mail_sources.py`: the share
results are written before the mail step; the mail step runs as its own process with a
ten-minute deadline (`mail_step`, `MAIL_TIMEOUT`) and a timeout is reported as
"TIMED OUT" rather than lost; and `_outlook()` attaches to the running Outlook with
`GetActiveObject`, which fails at once while Outlook is starting, and only launches a
windowless instance with `Dispatch` when none is running. Pinned by four tests in
`tests/test_watch_sources.py`, including that the report and inventory exist on disk
before the mail step is entered.

Run by hand today after the diagnosis: 6 copied (1218 and 1549 DCOs and ODD extracts,
1539 and 1549 September workbooks), 4 superseded removed, mail step 0 to take.

**No figure moves.** A morning's landings now reach `Inputs/` even when Outlook is busy.

### 2026-09-10 — the dashboard shows build READINESS, not just what was built

Three changes to the "RPE Client Performance" artifact (Aaron, 2026-09-09/10).

**"Clients and decks" became "Build readiness · <period>".** It listed the newest deck
BUILT; what is in front of you at the start of a cycle is what CAN be built and what is
missing. Each row now reads ready or blocked, names what it is blocked on, and shows one
chip per required input — carrying that product's colour, red with a cross when missing,
amber when stale, with the detail in its tooltip. The header counts `N of M ready · K
built`. Austin reads "blocked: ARS workbook", which is the true answer for that client
today.

The readiness comes from `deck_status.collect()`, not a second implementation, so this
page and the delivery dashboard cannot disagree about whether a client is ready. It
degrades to "not checked" rather than failing the refresh — which is what the five
CashPlease-only clients show, since they are not on the roster `deck_status` reads.

**The provenance footer is a bulleted list**, one line per program, plus a new Build
readiness line naming its sources and stating that the CSI shares are not checked there,
so readiness reflects what is on this machine. It was a single dense paragraph carrying
five different sourcing rules.

**A "Last updated" pill sits under the title.** It carries the time as well as the date,
because the page can be refreshed several times a day; `content_hash` already excludes
`generated`, so the timestamp cannot cause a spurious republish.

### 2026-09-09 — branch-chart rate labels moved into a band above the line

They rode their own markers, which put them in the gap between the rate line and the
bars — and that gap closes exactly where a branch is both large and typical. True Sky's
377-account branch topped out a hair under its own 81% label on the personal take-rate
slide, shipped this morning.

The labels now sit at one constant height above the line. A bar cannot reach them,
because the bars are held to the lower band by their own headroom, and each label is
still directly above the branch it belongs to. The halo stays: on a chart whose rates
run near the top, the line passes beneath the band and must pass behind a number rather
than through it. `tests/test_branch_chart.py` watches where the text is actually drawn.

Affects all four branch charts. **No figure moves**; the decks in `Outputs/` carry the
old placement until they are rebuilt.

### 2026-09-09 — no backup copy; the original sources are the backup

Reverses this morning's write-only-backup decision (Aaron, 2026-09-09). There is no
second copy of the pipeline tree and nothing syncs it anywhere. Every input can be
re-fetched from where it came from — the CSI shares hold the ODD extracts, DCOs, ARS
workbooks and MRPCPM analyses; the mailbox holds the MRPC / CashPlease reports and the
ICS workbooks — and `watch_sources.py --copy --mail` is how they come back. Outputs are
rebuildable from those inputs by definition, and `Outputs/Archive/` keeps every
superseded deck.

Google Drive is gone from the project: **~236 references across 20 files**, including a
set of code identifiers that had become actively misleading once the tree moved —
`drive_glob`, `rec["drive"]`, `drive_odd`, `_drive_periods`, `--no-drive`, `drive_state`
— all naming a location nothing used any more. Also removed: `.env.drive.bak`, the Mac
Google-Drive example root, and the Drive-streaming hints in `rpe_env`'s error messages
("mark it available offline"), which advised a fix for a problem that can no longer
occur.

**This file is deliberately untouched** (Aaron, 2026-09-09 — "keep the changelog, strip
the rest"). Its purpose is that a reversal is findable, and the move off Drive is exactly
such a reversal; scrubbing it would erase the account of how the pipeline got where it
is. `docs/PRD-2026-08-26-…` is marked superseded at the top for the same reason — its
body describes the Drive era accurately and rewriting it would falsify a dated document.

**No figure moves**; `deck_status 2026.09` reports the same 15 clients / 11 ready / 10
built, and the watch and mail steps run unchanged.

### 2026-09-09 — the daily run takes the inputs that arrive by email

MRPC and CashPlease reports (Bradford Sanders) and ICS workbooks (Matt Milliman) never land
on the CSI shares. `deck_status` has said "arrives by email / n/a" for the ICS workbook
since 2026-08-31 because there was no source-side signal to wait on. There is one now.

`scripts/mail_sources.py` reads Outlook over COM — chosen over Graph because the scheduled
task already runs as the logged-on user, so there is no app registration or consent to own
— and `watch_sources.py --mail` runs it as part of the 08:00 check. The task now passes
`--notify --copy --prune --mail`.

Findings from building it, each of which is now a rule:

- **The Inbox is not where these live.** A 45-day Inbox scan read 35 messages and 123
  attachments and found neither sender: a rule files them into **Archive**. The scan covers
  Inbox and Archive plus subfolders.
- **An Exchange sender's `SenderEmailAddress` is an X500 `/o=` path**, not an address, so
  matching on it accepts nobody. Resolved through the Exchange user, then
  PR_SENT_REPRESENTING_SMTP_ADDRESS. Matching is on the SMTP address only — a display name
  is spoofable — and each sender may supply only their own kinds.
- **Only the newest of each thing.** A 120-day scan proposed 25 files; twenty were
  superseded weeklies the pipeline never reads and `--prune` would have deleted the same
  run, and one was a 2026.05 ICS workbook for a client already holding 2026.07. With the
  rule applied: **1 file to take, 21 skipped, each with its reason.**
- A local copy written after the message arrived is not clobbered — the same
  recalculated-workbook guard the share copier has.
- An attachment whose name does not match `<id>-<period>-<kind>` is parked in the legacy
  folder and reported.

Read-only throughout: nothing is marked read, moved or deleted. An unreachable mailbox is
reported and skipped rather than failing the share check. 24 tests, all driving an injected
message list so they run without Outlook.

### 2026-09-09 — the pipeline runs locally; Drive is a write-only backup

`RPE_DATA_ROOT` is now `C:\Data Pipelines\RPE Pipeline` (Aaron, 2026-09-09). The tree
moved with robocopy — **308 files, 1.229 GB, 0 failed, 0 mismatch** — and was verified by
file count, byte total per folder and hashes on a sample before `.env` was repointed.
`deck_status 2026.09` reads identically from the new root.

No code changed: every path resolves through `rpe_env`, which is the whole reason that
indirection exists. What did change is the documentation that would have undone it —
CLAUDE.md said "Google Drive is the source… on every machine" and, separately, **"do not
point `RPE_DATA_ROOT` anywhere under `C:\Data Pipelines\`"**. Both are rewritten, with
the old rule kept as dated history and labelled so it is not "corrected" back, plus a note
that `Renewals Pipeline` is a different project sharing that parent. `.env.example` too.

**One source, always**: the backup direction is local → Drive and never the reverse. A
file read back from Drive recreates the two-stores problem that shipped month-old ICS
figures in August. *Nothing pushes local → Drive yet — that mechanism is still to build.*

### 2026-09-09 — inputs are sorted into a folder per kind

Everything landed in one flat `Inputs/ARS & MRPC Reports/` — DCOs, ARS workbooks, MRPC
analyses, ICS workbooks, ICS Charts and the weekly summaries together, 55 files deep, with
the kind readable only from the filename. `scripts/watch_sources.py` now files each copy
by kind on arrival:

| Kind | Folder | Existing files moved |
| --- | --- | --- |
| DCO | `Inputs/DCOs/` | 17 |
| ARS workbook | `Inputs/ARS Workbooks/` | 10 |
| MRPCPM analysis | `Inputs/MRPC Analyses/` | 6 |
| ICS workbook | `Inputs/ICS Workbooks/` | 8 |
| ICS Charts | `Inputs/ICS Charts/` | 12 |
| Weekly summaries | `Inputs/Weekly Summaries/` | 2 |

All 55 classified, none unrecognised, moved rather than copied. `Inputs/ODDD/` is
unchanged.

**`rpe_env.INPUT_KIND_DIRS` is the only place the folder names live.** Readers resolve
through `rpe_env.report_dirs()` / `report_files()` — `build_month`, `deck_status`,
`build_ics_gen`'s workbook-period check and the dashboard refresh all changed from globbing
one literal folder to globbing the set. The set still includes the old flat folder, for
good, so a file dropped there by hand still resolves and the sort never had to be perfect.

Two rules the copier keeps: a file Inputs/ already holds is replaced **where it is**, so
sorting cannot create a second copy of a workbook sitting in the legacy folder; and prune
compares names across every folder, since a superseded file and its replacement no longer
share one.

**No figure moves**; `deck_status 2026.09` reports the same 15 clients / 11 ready / 10
built before and after.

### 2026-09-09 — the source-watch report said "Drive" while writing to C:

After the move the daily report still read *"not yet current on Drive"*, *"Drive: differs"*,
*"Would copy to Drive"*, *"Copied 1 to Drive."* — describing a destination it no longer
used. 19 strings corrected, four test assertions with them. The destination itself needed
no change: it was always `rpe_env`'s answer, never a literal.


### 2026-09-08 — the Summit one-pager and the monthly deck now share one before/after

Aaron: "the Summits and the regular delivery decks should use the same logic." They did
not. `responder_activity.py` (the one-pager) claimed in its own docstring to mirror
`metrics_gen` (the deck) "so the one-pager agrees with the client's deck instead of
restating it", and differed in four ways at once:

| | deck | one-pager |
| --- | --- | --- |
| cohort | every personal responder | only those still `Elig=Yes` at the snapshot |
| after window | 6 fixed months | every month to the end of the extract |
| winsorizing | ONE cap over before+after | a separate cap per window |
| headline | pooled over responder-observations | mean of the per-mailing means |

Every difference pushed the same way. On True Sky 1676, measured against the same
extract on the same day:

| | one-pager (was) | deck, and one-pager now |
| --- | --- | --- |
| responder spend | $459 → $999 (**+118%**) | $467 → $947 (**+103%**) |
| responders | 8,153 | **9,962** |
| customers reached | ~510 / mailing | ~623 / mailing |
| mailings | 15 | 12 |

A Summit attendee could have been handed a one-pager saying +118% while their own
monthly deck said +103%, and 1,809 responders — 22% of them — were missing from the
one-pager because they had closed or gone ineligible since responding. That is the
survivorship filter `metrics_gen` dropped on 2026-08-27; the one-pager kept it.

**The fix is one function, not two matching ones.** `build/ars_pipeline/before_after.py`
holds the measure — cohort, window ladder, winsorizing, pooling, the offer split and the
NSF/OD figures — and both entry points call it. It is import-safe, like `odd_rows`:
importing `metrics_gen` RUNS it (`sys.argv` at module scope), which is the hazard that
made the one-pager re-implement everything in the first place.

Verified behaviour-preserving for the deck: rebuilding 1676 before and after the
extraction gives **121 metric keys identical, none differing**, plus one new key the
one-pager needs. `tests/test_before_after.py` pins each decision and that neither caller
keeps a copy. Also fixed while there: the one-pager's method note described the old
window and cohort as fixed text, and its two headline tiles hardcoded a `+` sign that
would have rendered "+-5%" on a decline. `responder_activity` now also keeps the `MTD`
column, without which its NSF/OD figures would have come back 0 while the deck reported
them.

### 2026-09-08 — responder before/after now measures 6 months after the mailing

Both Responder Activity charts (Before vs After Mean, and by Offer) compared a 3-month
baseline against the **3** months after each mailing. They now compare it against the
**6** months after (Aaron, 2026-09-08).

Measured across all nine ARS clients first, on the mailings every window supports so
that window length was the only difference. The gain decays, consistently, and three
months does not show it:

| Client | Threshold gain, 3 mo | 6 mo | all months after |
| --- | --- | --- | --- |
| 1038 Sugar River | +50% | +44% | +39% |
| 1075 Austin | +50% | +45% | +40% |
| 1204 FSB Michigan | +77% | +68% | +63% |
| 1509 Texas Bay | +93% | +83% | +71% |
| 1537 Brooks Bank | +83% | +73% | +69% |
| 1539 Marine | +81% | +71% | +63% |
| 1676 True Sky | +97% | +86% | +78% |
| 1705 CoastLife | +71% | +62% | +55% |

Six months still shows the lift holding well clear of baseline, which is the durable
claim; three months reads closest to a spike. **"All months after" was rejected**: each
bar's window is a different length — the oldest mailing averages 30-plus months, the
newest one — so the bars decline left to right partly by arithmetic. That is the defect
the fixed window was introduced to fix.

Cost: the newest one or two mailings drop out (True Sky 14 → 12; the axis now ends Jan
2026, not Mar 2026). A young program falls back down a ladder that shrinks the AFTER
side first — the baseline is what the comparison is anchored to, so it gives ground
last — and both lengths are recorded (`ba_before_months` / `ba_after_months`) and stated
on the slide, so a 3-and-1 comparison is never passed off as a 3-and-6 one. The chart
legend derives from them too; it read "After (3-mo window)" as a constant.

True Sky 1676: pooled Threshold **$548 → $1,078 (+97%)** becomes **$547 → $1,015
(+86%)**; the Mean slide's headline **$467 → $947 (+103%)**.

### 2026-09-08 — "NSF/OD activity stayed roughly flat" was canned; it now carries figures

That clause sat, as fixed template text, beside the NSF/OD panel of the very chart that
measures it. It is the sentence behind the Marine FCU correction and Aaron's +/-2% rule
(2026-08-31) — the rule was written, the sentence was not fixed.

It now follows the data and states the figures: within +/-2% reads "almost flat", a rise
states the increase, a fall says the mailings did not have an impact on NSF/OD activity.
`metrics_gen` pools NSF/OD items per responder per month across every responder-mailing
observation, unwinsorized, so the clause agrees with the panel beside it.

**True Sky 1676 was not flat**: 0.33 → 0.36 items per responder per month, **+9%**. The
slide had been saying otherwise.

Also derived: "Debit spend rose after every mailing" is a claim about all of them, so it
is now made only when it is true of all of them, and states the count when it is not.
(True Sky: 12 of 12.)

### 2026-09-08 — branch charts: no program-average line

Removed from all four (Aaron, 2026-09-08). The figure is the donut on the Reg E slides
and the 12-Mo Take Rate tile on the take-rate slides, so the dashed rule was a third
rendering of a number already twice on the slide. The four captions dropped their
"Dashed line = X% …" sentence in both `ars_template.pptx` and
`multi-product_reference_deck.pptx`, and the builder swaps that filled that figure in
are gone — a swap matching nothing fails the build, which is what would have caught a
half-done version of this. `tests/test_branch_chart.py` watches for the `axhline` call
rather than reading the source, so a line reintroduced by any route fails.

### 2026-09-08 — branch charts: accounts in the bars, rate on the line

The four branch charts — 12-Month Take Rate Personal (image11), Business
(biz_branch), Reg E All Personal (image14), Reg E Last 12 Months (image16) — drew the
RATE as the bars. A rate without its denominator is not readable: a branch with 15
accounts and 4 opt-ins drew exactly as tall as one with 900 accounts at the same
percentage. Accounts opened now set the bar height and the rate is a line on its own
axis. (The program average was kept as a dashed reference at first and removed the
same day — see the entry above.)

What it surfaces: on True Sky 1676, branch **1004 is the largest by a distance — 513
of the last twelve months' accounts, roughly twice the next branch — and the worst on
new-account Reg E opt-in at 8%** against a 14% book. The old chart drew it as the
shortest bar on the slide and said nothing about its size.

Details: one renderer (`chart_lib.branch_chart`) now serves all four — `c_rege_branch`
had its own near-copy that had already drifted on halo, headroom and tick sizes. The
account count sits under the axis beneath its branch number rather than above the bar,
because above is where the rate line lives and the two collide exactly when a big
branch has a low rate. The average line was grey rather than the series colour so it did not
read as a second line where the two cross — it was removed outright the same day (see
above). The rate axis stops at 100%: 1.30x label headroom over a 99% peak
had been printing a 120% tick. The business chart's line is TEAL over its navy bars
(STYLE.md — a mark is never drawn in the canvas colour).

**No figure moves**; the bars now carry a second measure that was not on the slide.

### 2026-09-08 — five ARS charts never adopted `MMM'YY`; a render-time guard now enforces it

`mon_yy` settled the axis format on 2026-09-01 and three ARS charts adopted it. Five
did not, because they build their labels by string-slicing and so call no formatter
for anything to check:

| Chart | Slide | Drew | Now |
| --- | --- | --- | --- |
| `c_before_after_split` (image31) | Before vs After by Offer | `Feb24`, flat | `Feb'24`, 45° |
| `c_before_after` (image10) | Before vs After (Mean) | `Feb24`, rotated 90° | `Feb'24`, 45° |
| `c_sustained` (image9) | Sustained Respondent Activity | `Sep '23`, 30° | `Sep'23`, 45° |
| `c_monthly` (image5) | Monthly incremental revenue | `Aug` — **year discarded** | `Aug'25` |
| `c_ranking` (image6) | Ranking by Tier (y-axis) | `Sep 2023` | `Sep'23` |

`c_monthly` was the one that could mislead: `m.split()[0]` threw the year away on a
12-bar axis that spans two of them, so `Aug'25` and `Aug'26` would have been
indistinguishable had the window ever covered both.

**The check.** `periods.install_month_axis_guard()`, called at the top of all three
chart modules, wraps `set_xticklabels` / `set_yticklabels`: a label `parse_month`
recognises must already equal its `mon_yy` form, or the render raises
`MonthAxisError` and the build stops. It runs where the label is DRAWN because that
is the only place the value exists — a source lint sees `cats`, not `"Feb24"`.
Categories that are not months (branch numbers, offer tiers, age bands, `2025 YTD`)
pass through untouched. `tests/test_chart_axes.py` pins both directions.

`periods.parse_month` also now reads `Sep '23` (space *and* apostrophe). It was the
form Sustained actually drew and the one form the parser could not read, so the guard
would have looked straight past the chart that prompted this.

**No figure moves**; five axes change how they read.

### 2026-09-08 — the ARS builder refuses an unevaluated workbook

`build/ars_pipeline/base_guard.py` holds the one check (at most one month in the
program, no lifetime revenue, no current revenue = the template's defaults). Both
extractors (`extract_base_gen.py`, `base_tab_extract.py`) and `build_ars_gen.py` exit
with `UNEVALUATED WORKBOOK: <file> ... open it in Excel, save, and rebuild` instead of
producing a base of zeros; the dashboard refresh imports the same function and reports
the row. `tests/test_base_guard.py` pins that every ARS entry point uses it.

Why: the guard the dashboard got earlier today would have caught 1539's $0 page and
let the same workbook build a deck saying Marine FCU has run ARS for 1 month with $0
in revenue, in prose, on slide 6. Nothing on the deck would have flagged it — a
month-1, $0 client is a shape the builder accepts.

**No figure moves**; a build that would have shipped zeros now stops.

### 2026-09-08 — the copy step overwrote a recalculated workbook; it no longer can

The first `--copy` run replaced Drive's `1539-2026.08-Marine FCU-Workbook_v2_1_0.xlsx`
with the share's copy because the two differed in size. The share's copy had never
had its formulas evaluated — Executive Financials MM read "Months in the Program: 1,
Mailings to date: 0" and every revenue cell 0 — while the Drive copy had been opened
and saved in Excel, which is what gives the extractors values to read. The dashboard
rebuilt from it showed Marine FCU with $0 revenue; a deck built from it would have
too. Recovered by recalculating the Drive copy in Excel (COM, `CalculateFullRebuild`,
save): months 96, mailings 38, current revenue $154,881.24, matching the shipped deck.

Two guards: `copy_plan` now overwrites a "differs" file only when the SOURCE is the
newer write (a real re-landing); a Drive copy modified after the landing is a
deliberate change and stays. And `refresh_performance_dashboard.uncalculated()` reports
a workbook whose base extracts as one month, no mailings and no revenue as "carries no
calculated values — open it in Excel and save", instead of rendering zeros.

Open question for Aaron: whether other landed workbooks arrive unevaluated too. The
seven September workbooks copied today all carry values; 1539's August one did not.

### 2026-09-08 — the performance dashboard shows each client's newest figures, not one cycle's

`refresh_performance_dashboard.py` picked the ARS workbook, the figure sidecar and
the decks by the cycle period alone. The first September rebuild showed what that
costs: three ARS clients (1075, 1539, 1549) lost their section because their
September workbook had not landed, every client read "not built" because no
September deck exists, and every mailing-response cell went blank. It now takes,
per client, the newest ARS workbook, the newest shipped-deck sidecar and the newest
built deck at or before the cycle period, and the page tags a row whose workbook or
deck is older than the cycle ("workbook 2026.08", "built 2026.08 — no 2026.09 deck
yet"). The footer reads its source lines from the dataset instead of carrying dates
by hand. The scripted 2026.09 page: seven ARS clients on September workbooks, three
tagged August, all decks tagged August.

**Figures move on the page**: the seven September workbooks carry August data, one
month on from what the page showed. Nothing client-facing is touched.

### 2026-09-08 — superseded inputs are deleted from Drive

`watch_sources.py --prune` (passed by the "RPE Source Watch" task after `--copy`)
deletes a file in `Inputs/ARS & MRPC Reports/` when a newer version of the same thing
is there: same client and kind with a later period, or the same weekly family with a
later stamp. The newest is always kept, a lone file is never touched however old, a
tie (a weekly and its "- Copy") keeps both, and the ICS Charts workbooks, ODD extracts
and anything unpatterned are out of scope. The first run removed 53 files (the
2026.07 and 2026.08 DCOs, ARS workbooks and MRPCPM analyses that 2026.09 landings
superseded), leaving 55.

Why: Aaron asked (2026-09-08) that old versions go once an updated input exists.
Every builder resolves the newest file for its period, so nothing reads the pruned
ones; the one visible effect is that the delivery dashboard's input columns for a
past period now read "not copied" — that period's decks are built and sent, which is
the column that matters.

### 2026-09-08 — the daily source check now copies roster clients' files to Drive

`watch_sources.py --copy` (passed by the "RPE Source Watch" task) copies every file on
the CSI shares for a roster client that Drive lacks or holds a different landing of into
`Inputs/`: DCOs, ARS workbooks, MRPCPM analyses and ICS workbooks to `ARS & MRPC Reports/`,
the ODD extract to `ODDD/<id>_ODDD.zip`. Copy-only, `.part`-then-rename, size-verified.
The ODD extract is copied only from the NEWEST month on the share per client: with two
months scanned and no period in the Drive filename, last month's extract at source
"differs" from Drive forever once this month's is copied, and copying it back would be
the stale-ODD failure this pipeline guards against everywhere else.

Why: Aaron found 26 September files sitting in his `Velocity_clientreports` folder that the
watch had recorded at its baseline and nobody had copied; Drive held zero 2026.09 files
and the performance dashboard was still on 2026.08. The first `--copy` run moved 37
files (13 DCOs, 7 workbooks, 4 MRPCPM analyses, 13 ODD extracts) for the 15 roster
clients; 1437 Canandaigua's files were left on the share because `clients.md` ends it.

**A client-facing figure can move as a result** — that is the point: the next build and
the next dashboard refresh read this month's inputs instead of last month's.

### 2026-09-08 — the performance dashboard artifact refreshes itself after the source check

`scripts/refresh_performance_dashboard.py` is the aggregator behind the "RPE Client
Performance" artifact, promoted from a per-session scratchpad script into the repo
so a refresh is reproducible: ARS figures through `extract_base_gen` / `base_tab_extract`
and the shipped deck's figure sidecar, ICS and MRPC from the VIP sheets, MRPC and
CashPlease from the newest weeklies (CashPlease through that repo's own `cp_extract.py`).
It injects the dataset into `scripts/perf_dashboard_template.html` (the artifact's
page, checked in) and reports `STATUS: changed|unchanged` against the hash last
published. The Claude scheduled task `rpe-dashboard-refresh` runs it daily after the
08:00 source watch and republishes the artifact in place only when figures moved.

Verified: the scripted dataset reproduces the hand-built 2026-09-08 artifact figure for
figure; the one addition is the CashPlease peer cohort's DDA fields, now populated
because the extractor is given the DDA counts the CashPlease pipeline already keeps.
The page does not render those fields, so nothing visible changed on the republish.
The period is derived from the newest ARS workbook on Drive (2026.08 today) rather
than assumed from the calendar — the same rule the monthly decks follow.

### 2026-09-08 — a daily check of the CSI shares for new inputs

`scripts/watch_sources.py` scans this month's and last month's folders on
`\\PADMIS105\Velocity_company\Aburgard\ODDD` and `\\PADMIS105\Velocity_clientreports`,
diffs the inventory against the one it saved last run (`Build Artifacts/source_watch.json`),
and reports what is new, re-landed or gone — roster clients first, each with whether
the Drive copy the builders read is already current. `scripts/register_watch_task.ps1`
schedules it as the Windows task "RPE Source Watch", daily at 08:00, with a toast
when there is news. Registered on Aaron's Windows machine the same day; the first run
recorded a 309-file baseline.

Why: `deck_status.py` says whether a file is there now, and a morning glance at the
dashboard misses the straggler — 1174's 2026.08 extract landed four days after the
batch, 1502's 2026.09 extract six days after, and a re-landed extract (1539, 2026.09)
keeps its name. Two rules carried over from the dashboard: off VPN the shares are
unknown, not empty (the run exits 2 and leaves the inventory alone), and a damaged
inventory is refused rather than read as "nothing seen".

**No client-facing figure moves; nothing is copied to Drive automatically.**

### 2026-09-02 — CashPlease gets its own shell

`templates/cashplease_template.pptx`: a 10-slide Union Financial demo (cover, Summit,
one-row agenda, divider, the four CashPlease content slides, Questions, Contact),
materialized by running `build_cp_gen.py` on a synthetic pack for client 999 with
invented figures and a dummy source filename. Until now the CashPlease builder
started from `ars_template.pptx` as a bare shell and stripped 42 slides and 33 media
files on every build, and the CashPlease look had no template of record to diff
against. The shell now goes through the gate like the other three, and the layout
baseline carries it. `build_all_cp.py` points at it. Verified: the dummy pack and
1734 Altamaha both rebuild from the new shell at 0 FAIL, and an ICS-CP deck
assembles from the shells.

**No client-facing figure moves, nothing renders differently.** The five CashPlease
slides are built from the pack either way; the shell only supplies the theme,
masters, embedded fonts and the five shell slides it always did.

### 2026-09-02 — the style guide, the gate and its companions, cleaned up

`templates/STYLE.md` was rewritten as one document (this supersedes the 17:49 reorganization below, done in a parallel session and merged into it: its verified facts — Excluded Accounts open-only, the ICS one-decimal row, label halos and axis striding, the builder-inserted slides — are carried here) with a scope table (Executive
Reviews, the CashPlease module, the ILS review prep slides, the Summit one-pager),
an enforcement map naming the file behind every rule, and a dated decision log
replacing the per-date reversal notes that had accreted through the body. Stale
content went: the 2026-07-10 Austin per-chart to-do list (all fixed by 07-24),
`style_tables.py` and `kickoff_lib` (retired), `build_gen`/`build_gen_b`, the
two contradictory MRPC tier-color sections, and a divider line the shells never
carried ("Program Performance Review" — the ARS shell reads "Mailings · Debit Card ·
Reg E"). `templates/TEMPLATES.md` lost the superseded 67-slide Marine map and now
tables the three shells with their slide counts, plus the two families that have no
shell (CashPlease, ILS prep). `tests/test_style_doc.py` fails the suite if either
document cites a repo path that does not exist.

`validation/validate_deck.py` was restructured: every rule is a named function
listed in `RULES`, `run()` returns the findings, and the inline rules that lived in
`main()` are now `text_rule_findings`, `geometry_findings`, `autofit_findings`,
`mailing_table_findings`, `extract_findings` and `labelled_metric_findings`.
**Output is byte-identical** on all four templates and all seventeen 2026.08 decks
on Drive, checked by diff. One rule was added.

**Text drawn over text now FAILs.** Ported from the CashPlease project's `cp_qa.py`:
its Peer Comparison footnote was pulled up by `fit_layout` onto a row of capsule
pills and this validator returned 0 FAIL, because every overlap rule it had looked
for text over a CHART. The port compares estimated GLYPH boxes rather than frames —
per paragraph, at that paragraph's size, placed by alignment and vertical anchor.
A frame comparison flagged 109 places on the shipped decks (every ARS title box
overlaps the selection line's box by 0.10"; the ICS education titles sit in boxes
two inches tall; an ICS callout stacks 40 pt over 16 pt); the glyph comparison
flags none of them and still catches the 0.56" footnote. `tests/test_validate_deck.py`
carries both halves.

`validation/qa_all.py`: argparse, and the unit suite is no longer skipped quietly.
The Windows Store python has no pytest, so a gate started with plain `python`
reported PASS having run zero tests; it now prefers the repo `.venv` interpreter
for both pytest and the validator, and prints a banner when the suite could not run.

**Every MRPC and ICS deck renders differently, by two alpha points, and no figure
moves.** The callout drop shadow is now defined once, `shapes.shadow`, and the ARS,
ICS and MRPC builders import it. The ICS builder had its own copy at alpha 26%
against 28% everywhere else — a drift STYLE.md described as "matching".

Docstrings in `build/fit_layout.py`, `build/restyle_fonts.py` and
`build/slide_geometry.py` now state what the code does (the dense-table titles,
the geometry rules per title, the numbers `fit_layout` uses), and `build/README.md`
no longer lists the `data/` folders deleted 2026-08-29.

Not fixed, reported: `build/assets/summit_slide.pptx` is gitignored by the blanket
`*.pptx` rule and is absent on the Windows machine (no Drive `Inputs/Summit/`
either), so the four `tests/test_summit.py` cases fail here and every ICS/MRPC
build would. The asset needs committing (an ignore exception) or copying to Drive.


### 2026-09-02 — the ODD fixture regenerates when its generator changes

`conftest` only built the synthetic ODD when the file was missing, so pulling a change to
`make_odd.py` left a stale CSV in place. When MTD changed from fee dollars to NSF/OD item
counts, a cached fixture failed three correct tests with "non-integer MTD values" — pointing
at the tests rather than at the fixture. It now regenerates whenever the generator is newer
than the file.

### 2026-09-02 — STYLE.md reorganized, and three contradictions in it resolved

The style guide had accreted chronologically — thirty flat sections with headings like
"Slide-check additions (round 2)" — which reads as a changelog rather than something a
colleague can look something up in. Reorganized into eight numbered sections plus an
appendix, with a table of contents: foundations, slide anatomy, the two months, elements,
deck structure, per-product rules, adapting to client data, enforcement.

**The MRPC tier colours were stated three times and disagreed with each other**, and
`build_mrpc_gen.py`'s own docstring stated a fourth, superseded version. The code is the
truth — Gold = orange, Platinum = steel `#9DB8CC`, Business = navy, and the callouts MATCH
the bars. Stated once now, as a table, and the docstring is corrected.

The colour list also named `STEEL #9DB8CC`, but `brand.py` has `STEEL = #7B9BB8` (ARS) and
`STEEL_SOFT = #9DB8CC` (ICS/MRPC). The palette now matches `brand.py` name for name, so a
reader who copies a name gets the colour they read about.

Promoted two things to their own sections because they are the mistakes that actually
recur: **the two months** (reporting vs data, the distinction behind several defects) and
**enforcement** (what runs, in what order, and the three rules learned the hard way).

Dropped the nine "Known per-chart fixes (Austin 1075 review, 2026-07-10)" — one-off bug
reports rather than style rules, and the builders have moved past them. Added this week's
rules: Excluded Accounts is open-only, the ICS one-decimal comparison, chart striding and
label halos, and a note that Product Mix, Excluded Accounts and Reg E by Branch are
INSERTED by the builder, so they appear in a built deck but not in the template shell —
which is not obvious from opening the shell.

Divider lines, Reg E slide titles and Responder Activity titles were verified against the
templates and a built deck rather than carried over on trust.

### 2026-09-01 — MRPC Enrollment Performance was drawn from an invented denominator

`chart_perf` read `new_checking_approx`, a key **no client sheet has ever
carried**, and fell back to `enrollments / 0.11` — a guessed 11% penetration. The
real counts sit in `new_accounts` and the real goal in `goal`, present in every
sheet. Because the goal line was derived from those invented bars, every month's
goal was wrong too.

On Austin 1075 the fabrication drew 1,036 new accounts for a month that actually
had 873; on Marine 1539 it drew 236 where the truth was 341. **Figures move on
every MRPC deck.** There is no fallback now — absent keys raise, because a chart
that cannot be drawn from the client's data must not be drawn from a constant.

Enrollment counts also moved from the line to **above the bar**, matching
Retention (Aaron).

### 2026-09-01 — every MRPC deck shipped the template's enrollment sentence

The Enrollment-vs-Goal caption was resolved by POSITION: `txt_at(S[4], top=6.7)`
with a 0.15" tolerance, against a box that sits at **6.40"**. `txt_at` returned
`None`, the `if` fell through, and the caption was never swapped — silently, with
no swap gate in the MRPC builder to catch it. Austin, Ideal, Summit, Capital and
Marine all shipped the same sentence: *"averages ~55% of goal, peaking at 72% in
Feb 2026"* — Union Financial's numbers.

It would not have worked anyway: the replacement read `penetration_summary` from
the client sheet with a `''` default, and no sheet carries that key, so a caption
that DID match would have read "Enrollment penetration ."

Now resolved by CONTENT, derived from `pct_of_goal` (which is present), and it
raises if either the shape or the series is missing. Marine reads "averages 58%
of goal, peaking at 78% in Jun 26". Geometry drifts; the words do not.

### 2026-09-01 — the ICS 12-month close rate was the client's NON-ICS rate

The Comparisons row was inverted. `client` carried the client's **non-ICS**
close rate program-to-date, while the client's own **ICS** rate sat in the
*Velocity average* column — so the row compared a client against themselves and
labelled neither side correctly. It went unnoticed because the first client it
was checked against, CoastLife 1705, happened to have a 6.7% ICS rate identical
to the Velocity benchmark.

The Velocity average is a **constant**, like the 29% of openings and $1,828
lifetime value beside it, read off the template's "Velocity Clients' Average"
column: `VELOCITY_CLOSE_RATE_12M_PCT = 6.7`.

The footnote had its own defect: it says "your Non-ICS accounts' **12-month**
close rate" and was handed the program-to-date figure. **Figures move on every
ICS deck with a current workbook:**

| Client | Row was | Row now | Footnote was | now |
| --- | --- | --- | --- | --- |
| 1075 Austin | 5.4 vs 51.7 | 6.7 vs 5.4 | 51.7% | 6.5% |
| 1509 Texas Bay | 8.3 vs 44.5 | 6.7 vs 8.3 | 44.5% | 15.3% |
| 1539 Marine | 6.9 vs 35.5 | 6.7 vs 6.9 | 35.5% | 10.4% |
| 1734 Altamaha | 7.9 vs 13.8 | 6.7 vs 7.9 | 13.8% | 9.0% |

Austin's deck previously showed a 51.7% close rate for their ICS programme; it is
5.4%, against a 6.7% benchmark. The stored `benchmark` block is written by
`ics_workbook_extract`, so the client JSONs were re-extracted — the diff was
exactly these three fields on all four clients.

### 2026-09-01 — life-of-account metrics use Last 12 Months only

Program-to-date spans the whole programme and answers a different question: on
Austin it reports a 51.66% non-ICS close rate against 6.45% over the last year.
Mixing the two windows in one table compares figures that are not comparable, so
every metric off the *Life of Account Data* sheet now reads the **Last 12
Months** row (Aaron). *% of Total Openings* moves with it — Austin from 25% to
32% (3,609 of 11,109 openings).

### 2026-09-01 — "a program high" was asserted, not found

Two ICS captions declared a record without testing for one. The Power-of-
Referrals line called the PREVIOUS month a programme high unconditionally, and
the Referral Trend caption said the same of whatever sat at `[-2]`. Both were
**false on every client checked**: Marine's July was 103 against a June of 129,
Austin's July 363 against 423, Texas Bay's July 40 against a March of 73.

The claim is now earned or dropped, and scoped to what the data can support —
`trend` is a 14-month window, not the whole programme, so nothing there can prove
a *programme* high. Marine reads "July brought 103; the last 13 months peaked at
129 in Jun 26." This is also the "no superlatives or unsupported claims" rule in
CLAUDE.md.

### 2026-09-01 — canned claims that future data can falsify

An audit of every string the three builders write into a deck, bucketed by how it
goes stale: fully canned, fixed-index, and interpolated-but-unearned. Three MRPC
sentences asserted something no one had checked:

- *"Revenue has grown across the life of the program"* — Capital Bank 1502 peaked
  at $8.4K and has fallen for three years. Now tested against the annual series;
  1502 reads "Life-of-program revenue reached".
- *"Monthly MRPC revenue has held around $XK"* — 1502 swings ±15% around its
  mean. Now claims stability only within ±10%, else "has averaged". (The average
  also printed at `,.0f`, so a $669 mean rendered "$1K" beside a "$0.6K–$0.7K"
  range — an average outside its own range. One decimal now.)
- *"Platinum ($14.95/mo) is the most-held card"* — both the leader and the price
  were hardcoded. Both now come from `card_billing`, so a client whose Gold or
  Business Platinum book overtakes Platinum is not told otherwise.

### 2026-09-01 — the gate FAILs a slide whose text contradicts its own figures

`validate_deck.claim_consistency_findings` reads one sentence at a time and
matches each claim to its NEAREST figure pair: a stated percentage against that
pair, a movement or flatness word against the change, a comparative against the
ordering. Flatness is held to Aaron's ±2% band.

Getting it to FAIL rather than advise took three corrections, each found by
running it over shipped decks rather than invented examples: a COMPARISON is not
a MOVEMENT ("lower balances than non-responders, $924 vs $2,477" is correct, and
reading it as a change looks like a +168% rise — that failed six correct slides);
a sentence carries more than one claim (testing every claim against the FIRST
pair failed six more); and negation ("did not increase" is not an increase).

A rule that flagged claims with no supporting figure was **dropped**: it produced
156 findings across 20 files, almost all legitimate bullets whose evidence is the
chart on the slide. A rule that cries wolf 156 times is a rule nobody reads.

Separately, the validator was truncating its own output — findings quote slide
text, and printing an em dash to a pipe on Windows raised `UnicodeEncodeError`
part-way through the report, so the summary line landed and every finding after
it was lost. A gate that cannot say what failed is not a gate.

### 2026-09-01 — Average Ticket describes what the figures actually did

The caption hardcoded "ticket **holds** through response" — true of the
template's own $50→$50 example and of nothing else. It shipped over declines of
5.2% to 8.6% on six 2026.08 decks (1509, 1537, 1539, 1549, 1676, 1705). The same
sentence hardcoded "monthly swipes **rise**"; real clients do rise, so that never
showed on a delivered deck until the golden deck's synthetic ODD fell 3.0% and
said "rise" anyway. Both verbs now derive from the values they introduce, on the
±2% band, as does the chart title above the bars in `ticket_chart.py`.

The closing clause — "the gain is more transactions, not larger ones" — was
dropped (Aaron, 2026-09-01). The two movements are stated; the reader can draw
that themselves.

### 2026-09-01 — one month format on every chart axis, and one overlay-line color

**Axes.** Every month label is now `MMM'YY`, angled 45° — `periods.mon_yy()` /
`axis_months()`. Three formats were in service and none agreed: ARS drew
`Jun'25`, MRPC drew `Aug 25`, and the ICS quarter panels drew `Jul` —
`mm.split()[0]` threw the YEAR away, so a 14-month axis read Jan…Dec…Jan. Fixing
it exposed a gap in the shared parser: `parse_month` never handled `Jun 25` or
`Jun'25`, the pipeline's two commonest forms, so every VIP series fell through to
`None`.

**Overlay lines.** Three goes at this. The MRPC Retention line was drawn plain
WHITE on the assumption it never left a navy bar — it does, and the line was
invisible for its whole length on the 2026.08 decks, legend swatch included.
Then navy with a white casing, which was legible but rejected on looks. Now
**teal `#0D9488`**, which needs no stroke: 4.02:1 against navy and 3.74:1 against
white, both clear of WCAG's 3:1, and close to the best any flat color can manage
against those two extremes (3.88:1). Orange reference lines are left alone —
they already read at 5.5:1 on navy. `tests/test_chart_colors.py` still fails the
build if a mark is drawn in the canvas color.

### 2026-09-01 — ICS Billed Expense drops the account count

"Billed Expense for 6,785 Accounts" wrapped onto the value beneath it. The count
was already conditional on `fits_one_line`, which passed 6,785 and let it wrap
anyway; it is now dropped unconditionally (Aaron). The same figure is already on
the slide in the "ICS Accounts" callout.

### 2026-09-01 — the ODD's `<mon> MTD` column is NSF/OD ITEMS, not fee income

`odd_rows.nsf()` documented the `<mon> MTD` column as "NSF/OD fee income", while
every consumer read it as an item count: `charts_gen` titles it "NSF/OD Items",
`metrics_gen` names it `items12`/`nsf_last_items`, and `build_lift_matrix`
multiplies it BY a per-item NSF fee. Two descriptions of one column, with the
dollar reading only in prose.

Checked against the 2026.08 extracts for 1539, 1705, 1204, 1075, 1549 and 1218
(~580k account-months): every populated `MTD` cell is a non-negative INTEGER,
frequencies decay smoothly from 0 through 1, 2, 3, ..., no value carries cents,
and nothing clusters on a multiple of any fee amount. `<mon> YTD` is the
calendar-year cumulative of the same integers (19,552 of 19,573 sampled 1539
accounts reconcile exactly against Jan..Jul MTD). The ODD carries no OD-fee
dollar column at all — NSF revenue reaches the deck from the workbook's
"Total NSF Revenue" via `base_tab_extract`. ITEMS is correct.

**No client-facing figure moves.** Nothing on a slide was computed from the
dollar reading; every deck consumer already treated it as items, and no template
slide carries "fee income" wording. This is entirely about what the number is
called. Renamed and corrected:

- `odd_rows.nsf()` — docstring now states ITEM COUNT, with the evidence.
- `lift_extract` — `fee12` -> `items12`. A `.pkl` cached before today must be
  regenerated; `build_lift_matrix` now says so instead of raising `KeyError`
  inside the valuation.
- `oddd_optimize` — `od_fee_income_MTD` -> `nsf_od_items_MTD`,
  `od_fee_income_YTD` -> `nsf_od_items_YTD`,
  `top_branches_by_od_income_latest` -> `top_branches_by_nsf_od_items_latest`.
  These were formatted with a `$` in `oddd_pack.md`, including in the DERIVED
  block labelled "for Key Metrics slide" — a mislabelled dollar figure sitting
  where a deck author would reach for one. Now printed as counts, with a line
  saying NSF revenue is not in the ODD. Nothing outside the script read the old
  keys. MTD/YTD/PYTD moved from `money_fams` to `num_fams`; both paths take the
  same sum, so the totals are unchanged.
- `.claude/agents/oddd-optimizer.md` — the sanity-check and pack-contents wording.
- `tests/fixtures/make_odd.py` — the fixture wrote `MTD` as `35.00`/`70.00`, i.e.
  two $35 fees, teaching the wrong meaning to every test built on it. It now
  writes small integers, and `YTD` as their calendar-year cumulative.

Standing-rule check added: `tests/test_nsf_is_items.py` pins the meaning from
both ends — the fixture data must keep the shape of a count (integers, count-scale
magnitudes, YTD >= MTD), and no module that reads the column may describe it in
money terms again. The guard is itself tested against the exact lines the defect
shipped as.

Incidental, same commit: `oddd_optimize` wrote `oddd_pack.md` and
`oddd_metrics.json` with the platform default encoding, so it died on Windows
with `UnicodeEncodeError` on the arrow in "mailed -> responded". Both writes are
now `encoding="utf-8"`. This was blocking all 26 `test_golden_deck` tests on this
machine.

### 2026-08-30 — Average Life of Account prints one decimal on both sides

The ICS Comparisons row compared a pair at two precisions: the Velocity average
rendered "6.9 Years" against a client "6.21 Years". `cfmt`'s `years` format used
`{v:g}`, which prints the shortest form — so it also gave a client at exactly 7 a
bare "7 Years". Both sides go through the one formatter, so `{v:.1f}` fixes the
pair. Affects 1075 (7.66 -> 7.7), 1509 (7.05 -> 7.0), 1539 (7.24 -> 7.2) and 1734
(6.21 -> 6.2); those four decks were rebuilt and reissued, one value each and
nothing else touched.

1537, 1632 and 1676 have no Comparisons slide to fix — their workbooks are 2026.06
and 2026.07 against a 2026.08 deck, so their financial detail is suppressed by the
stale-workbook rule. Checked rather than assumed, since "the slide is missing" and
"the fix broke the slide" look the same from the outside.

### 2026-08-30 — promote_month.py, and its archive stamp comes from the clock

The staging-to-Outputs step is now a script in the repo rather than one written
per run. It archives whatever a deck supersedes, and leaves a deck alone when its
rendered content is identical to the delivered copy — a rebuild that changed
nothing should not churn the archive and bury the copies that matter.

Its date stamp was a literal, which dated four archives to the wrong day and
collided with the previous run, producing "-2" and "-3" suffixes. Now derived from
today; the four mis-stamped files were renamed.

### 2026-08-29 — a whole deck is built in the test suite

`tests/test_golden_deck.py` runs the real chain end to end — oddd_optimize,
metrics_gen, charts_gen, build_ars_gen, restyle_fonts — on the synthetic ODD and a
new synthetic workbook extract (`tests/fixtures/make_base.py`). A pipeline
regression now surfaces in **9 seconds** instead of in a seven-minute run across
fifteen real clients. No client data is involved; both fixtures are invented and
generated on demand.

Assertions are structural, not a hash: a hash fails on every intended change and
teaches people to re-baseline without looking. What is pinned is what must not
silently move — it builds, all 28 charts render, the slide count holds at 49, the
expected slides are present, its own validator passes it, the provenance sidecar
is emitted, and no real client's name appears anywhere in it.

Building it exposed the fixture's own limits: eight branches over 800 rows left
every per-branch cohort under metrics_gen's 15-account threshold, so the Reg E and
take-rate branch tables came out empty and their charts had nothing to draw. The
fixture now uses three branches and a larger new-account cohort.

### 2026-08-29 — the Summit slide may come from Drive

`build/assets/summit_slide.pptx` is replaced by hand before each Summit by whoever
prepares it, who should not need a commit to ship it. `Inputs/Summit/summit_slide.pptx`
now wins when present; the committed copy is the default, so the common path
touches no network and cannot drift.

Everything else stays in the repo deliberately. Fonts are committed precisely so
both machines render identically; the template shells are versioned build inputs
whose geometry `qa_all` diffs against a baseline every run. Moving those to a
streamed folder would trade fast-and-identical-everywhere for a consistency the
pipeline already has.

The optional lookup caught a latent bug on the way in: `rpe_env` raises
`SystemExit` when `RPE_DATA_ROOT` is unset, and `SystemExit` does not inherit from
`Exception` — so an `except Exception` around an OPTIONAL lookup would have killed
the build on a machine that had never configured Drive.

### 2026-08-29 — README

The repo had a one-line README. It now says what the pipeline builds, how to build
a month, where data lives, and what each companion file decides — `CLAUDE.md`,
`clients.md`, `CHANGELOG.md`, `STYLE.md`, `TEMPLATES.md`, the agent docs and the
PRD — so the split between them is discoverable without reading all six.

---


---

## 2026-08-29 — 2026.08 monthly delivery

Everything the 2026.08 client review decks were built with.

The monthly reviews and the Executive Summit are two different deliveries: the
reviews go to every active client each month, the Summit runs a couple of times a
year and only for attendees (Aaron, 2026-08-29). This heading is the monthly one.

### 2026-08-29 — clients.md decides a client's name, and 1204 is renamed

1204 is **First State Bank - Michigan** (Aaron). It shipped as "FSB Michigan" while its
workbook said "First State Bank-MI" — three names for one client, none of them agreeing.

The roster's `Client` column is now the delivery name: it goes in the filename AND
overrides what the workbook carries, so the cover and every source note match. Renaming a
client is a delivery decision, so it belongs in the file where such decisions are recorded,
not inferred from a previous filename (which is how "FSB Michigan" survived a cycle) or
read off a workbook nobody chose.

Six other roster entries carried short forms that had never reached a deck — "Texas Bay
CU", "CoastLife CU", "Ideal CU", "WesBanco Bank", "FNB&T Chickasha", "Altamaha Bank and
Trust". They are aligned to the delivered names, so making the roster authoritative renames
1204 and nothing else. 1204's 2026.08 deck was rebuilt and reissued; the old file is
archived as `(renamed 2026-08-29)`.

### 2026-08-29 — the Summit slide stays, and its date parser is ready for the next one

Confirmed: every results deck carries the Executive Summit slide (Aaron). The slide is
replaced by hand before each Summit — Ft. Lauderdale is next, in November — so
`summit_date()` reads the date off the slide rather than hardcoding it, and now accepts
abbreviated month names and a range that crosses a month boundary. A format it silently
missed would fall back to the previous Summit's date, which is worse than failing.
`summit_period()` warns when the slide still names a Summit that has passed.

### 2026-08-29 — Excluded Accounts explains OPEN accounts only

The slide answered "why is any account on file outside ARS", so its largest bar was the
closed book — an account that is closed is outside ARS by definition and explains nothing.
Dormant and inactive accounts were a second bar, which conflates "this account is not
active" with "this OPEN account is not eligible". Neither is a reason.

The population is now the open book. Reasons are product code, no debit card, and an
account-level remainder. The closed and dormant counts are still computed and named in the
source note, so the scope is stated rather than implied.

The tiles now reconcile — open accounts = open-and-excluded + open-and-eligible. The
eligible tile counts OPEN eligible accounts and says so; the whole-book figure includes
dormant accounts the core still flags eligible (147 on 1204), which left the three tiles
147 apart with nothing on the slide to explain the gap.

### 2026-08-29 — a slide module's own source note is no longer overwritten

`build_ars_gen`'s note pass wrote a title-keyword note onto every slide, including the ones
Product Mix and Excluded Accounts had already written for themselves — losing the
population, eligibility column and scope those modules actually know. It now skips slides
whose module wrote a note. Not "skip any slide that already has one": the template shell
carries stale dummy-client notes that must be replaced.

### 2026-08-29 — ICS and MRPC read the VIP store, and only the VIP store

`resolve_client_json` no longer falls back to `build/{ics,mrpc}_pipeline/data/`, and those
folders are deleted. They held copies that drifted: the Drive store carried 2026-08-29
pulls while the repo still had 2026-08-10, and a build reading the repo shipped month-old
figures that validated perfectly because they were internally consistent. Two stores for
one fact is the problem. Every active ICS and MRPC client was confirmed present in
`Inputs/VIP Data/` first; the only files that existed solely in the repo were two
`_PARTIAL` captures the store's README already records as not copied.

### 2026-08-29 — two chart collisions

*Monthly Summary — Last 12 Months.* The orange average label was drawn with `va='center'`
on the dashed average line, so the dash ran through the text. It now sits just above the
line. The same dash also struck through any bar label near the average — `$284K`, `$282K`
and `$298K` on Austin — so bar labels carry a white halo and the line passes behind them.

*Responder Activity: Before vs After by Offer.* The axis labels the newest mailing on top
of a strided tick list, and appended it blindly. Austin 1075 has ten mailings and a stride
of two, so ticks ran `... 8, 9` and "Nov25"/"Feb26" printed on top of each other. The
neighbouring tick is dropped rather than crowded.


---

### 2026-08-29 — the figure sidecar now reaches the deck that ships

`build_ars_gen` names its sidecar after the deck IT wrote — the ARS component. For a
multi-product client that component is an intermediate; the deck that ships is the
combined one. `validate_deck` looks for a sidecar named after the deck in front of it, so
the FAIL-grade figure check silently did not run on any combined deck.

`assemble_combined` now merges each section's sidecar onto the combined deck. Measures are
prefixed with their program (`ARS:responders_latest_mailing`): two programs using one
measure name is coincidence, not identity, and pooling them unprefixed would invent a
conflict between unrelated figures. Within a program the check is unchanged.

### 2026-08-29 — a multi-product client gets the combined deck only

Recorded because the archive shows both shapes historically: some cycles delivered a
client's per-program decks alongside the combined one. The per-program decks are
intermediates that feed `assemble_combined` — one client, one deck (Aaron, 2026-08-29).

### 2026-08-29 — ICS Comparisons header fits the client name

"Altamaha Bank and Trust Company Data" is 4.64in of Montserrat 16pt in a 3.7in box: it
wrapped onto the value below. Shrinking is not available — `enforce_min_font` floors every
run at `MIN_PT`, which its own comment warns about. The header band now grows upward and
anchors to its bottom edge, so the values never move; a name that fits keeps the original
geometry and anchor exactly, and no other client's deck changes.

### 2026-08-29 — a missing MRPC channel count is not the same fact as a zero

Re-running all 15 2026.08 decks crashed Marine 1539's MRPC build: `chart_channel`
plotted `counts["Paper"] = None` and died on `vals + max(vals)`.

A channel count can be absent for two reasons and the chart must not conflate them. The
client may genuinely have no enrolments on that channel — a real zero, and a normal
state. Or VIP may decline to surface the number: Marine's Paper bar is too small to
trigger a tooltip, and the sheet records `None` with the note "~3 implied by 0.04%".
Writing `0` there would be false precision; the share is not zero.

Both now draw a zero-length bar and only the LABEL differs — the count when known, `0`
when the share is also zero, `n/a` when the share is non-zero but the count was not
readable. The totals chart is kept either way. A first attempt fell back to the share
chart whenever any count was missing, which threw away three good counts because of one
and read a genuine zero as a gap.

Affects Marine 1539 only: slide 58's Paper bar is now labelled `n/a` rather than `0`.

### 2026-08-29 — figure provenance sidecar: a measure renders one value, or the build fails

The 2026-08-28 Wellworth defect — the Jun 2026 drop reading 1,077 on the mailing slides and
1,026 on Reach/Depth/Ranking/Sustained — got past two guards. The builder's swap gate fails a
build whose swap string matched NOTHING, but here both swaps landed; they just wrote
different numbers. And `validate_deck.figure_identity_findings` has to INFER from wording
whether two figures are the same measure, which misfires on legitimately different cuts
(personal vs business take rate), so it can only advise.

The builder does not have to infer. It knows which measure produced each number, so it now
says so: `set_exact`/`set_shape_text` take an optional `measure=`, and `build/figures.py`
records (measure, rendered value, slide) as the deck is written. Two consumers:

* **Build gate.** `conflicts()` runs before the phase that materializes the output file, and
  a measure carrying two values fails the build with exit 2, naming both values and the
  slides they landed on. Placement matters — at the final save it still exited 2, but a
  partly-built deck was already sitting at the delivery path.
* **`validate_deck.figure_sidecar_findings`** reads `<deck>.pptx.figures.json` and FAILs on
  the same conflict. This is the FAIL-grade counterpart to the inferred rule, which stays at
  REVIEW: here the builder named the measure, so a difference is arithmetic, not a guess.

Naming is opt-in and only worth doing where one measure reaches more than one slide. Five are
named today (`responders_latest_mailing` across three slides, `mailed_latest_mailing` across
two, plus `resprate_latest_mailing`, `reach_total`, `dot_n`). No deck changes: 1204 rebuilds
to 49 slides, 38 chart images byte-identical, 0 text differences. Only the ARS builder emits
a sidecar; a deck without one validates exactly as before.

The sidecar goes to `Build Artifacts/` under `RPE_DATA_ROOT`, named after its deck, NOT
beside it: `Outputs/` is the delivery folder and holds finished decks only. `validate_deck`
looks there first and then beside the deck, so anything built before the move still
validates. The `.A/.B/.C/.D` phase decks no longer go next to the output at all — they are written to a
temp directory and dropped through `atexit`. They used to land in the delivery folder and
were only removed on the happy path, so a build that died partway left four intermediate
decks there. Cleanup alone would not have been enough: the CSI mount allows creating and
copying but NOT deleting (`rm` returns "Operation not permitted"), so nothing written there
could ever be removed. Verified both ways: a clean build leaves the output folder holding
exactly one file, and a failed one leaves it empty.

### 2026-08-29 — build from the template shell, never from a client deck

CLAUDE.md contradicted itself: one paragraph said each program "clones-and-swaps from the
latest Marine FCU (1539) reference deck", while its own file listing and every builder said
the input is the stripped `templates/*_template.pptx` shell. The builders were right — that
is what `build_ars_gen.py` takes as argv[1].

Cloning a finished client deck carries that client's numbers, captions, branch names and
speaker notes into the next client's file. It is the mechanism behind the reference-leak
rule and behind `validate_deck.reference_leak_findings` existing at all: a figure that was
never swapped is indistinguishable from one that was. Corrected in CLAUDE.md,
`templates/TEMPLATES.md` and all three deck agents, which also still named the retired
Client Presentations drop as the delivery target.

### 2026-08-29 — MRPC template shell carried misleading slide titles

`mrpc_template.pptx` titled two slides "MRPC Revenue to Union Financial" and two "MRPC Key
Metrics". They are four DIFFERENT slides — `build_mrpc_gen` retitles them by position to
Revenue by Year, Revenue by Month, Card Portfolio and Key Metrics — so no client deck was
ever affected, and a real build validates at 0 FAIL with four distinct titles. But a shell
that does not describe what it becomes is a trap for the next person reading it, and it made
the deck look like it shipped duplicate slides. The shells now carry the titles the builder
produces, in both `mrpc_template.pptx` and the reference deck. Built output is unchanged,
verified by rebuilding 1075 (13 slides, 0 text differences).

`assemble_combined.section_slides` also stopped resolving the opening block by position. It
dropped indices 1 and 2 outright, assuming every deck opens with cover + Executive Summit;
that holds for a BUILT deck of any program (summit_slide.py inserts one), so no delivered
deck lost anything — but it is not true of the MRPC template shell, which has no summit
slide and whose divider sits at index 2. Slides are now identified by meaning, as CLAUDE.md
requires: the cover carries the "Executive Review" line, the divider carries the program's
benefits line. Verified to produce identical results to the old rule on a built deck.

### 2026-08-29 — the reporting month comes from the period, never the clock

`build_ars_gen`'s slide-1 note and the one-pager header both took `date.today()`. Correct
only while a deck is rebuilt in the month it ships; rebuild an August deck in October and
the note said October while the cover still said August.

Both now resolve the same way, so a one-pager and its deck cannot disagree: `ARS_PERIOD` /
`RPE_PERIOD`, then the `<yyyy.mm>` tag in the output filename, and nothing else. An
unresolvable period is a hard failure naming both ways to fix it.

There is deliberately no fallback. Not the clock, for the reason above. And not the
Executive Summit's month either — that was tried and reverted the same day: a Summit runs a
couple of times a year and only for attendees, while these are the MONTHLY reviews, so
deriving one from the other would be wrong ten months out of twelve (Aaron, 2026-08-29).
`summit_slide.summit_date()` still reads the date off the slide, but nothing in a builder
depends on it.

STYLE.md draws the distinction and it is easy to invert: the cover and one-pager header
carry the month the report is PRESENTED (STYLE.md:85), while the period pills and PTD
figures carry the DATA month (STYLE.md:44, explicitly "NOT the report/generation month").

### 2026-08-29 — superseded: two reporting months came from the wall clock

The slide-1 speaker note (`build_ars_gen.py`) and the one-pager header
(`build_ars_onepager.py`) both took `date.today()`. Correct only while a deck is rebuilt in
the month it ships; rebuild an August deck in October and the note said October while the
cover, which resolves `PRESENT_MONTH` properly, still said August.

Both now resolve the reporting month the same way — `ARS_PERIOD`/`RPE_PERIOD`, else the
`<yyyy.mm>` tag in the output filename — so a one-pager and its deck cannot disagree. Note
that STYLE.md draws a real distinction here and it is easy to get backwards: the cover and
one-pager header carry the month the report is PRESENTED (STYLE.md:85), while the period
pills and PTD figures carry the DATA month (STYLE.md:44). These are the first kind.

### 2026-08-29 — blank `Business?` counted two different ways in one deck

`ticket_calc.personal()` read `!= 'yes'` while `metrics_gen.personal()` read `== 'No'`, so an
account with a blank `Business?` cell was PERSONAL to one slide and BUSINESS to another in
the same deck. `product_mix_slide` had already settled the house rule by splitting the book
three ways — Yes, No, and everything else — so a blank is neither.

Both now import one definition from the new `build/ars_pipeline/odd_rows.py`. Blanks are
real: 1218 carries 271, 1204 carries 57, 1038 carries 2. No delivered deck moves — the blank
accounts in 1038 and 1204 have no trailing-quarter swipes, so `ticket_calc` skipped them
anyway, and 1218 ships no ARS deck. 1218's blended average ticket would move $44.87 -> $44.79.

### 2026-08-29 — validator gained three rules and the gate gained a test suite

Nearly every entry above this one is a wrong-number bug, but `validate_deck` was a text and
geometry linter. Added, with the calibration each needed to stay quiet on a correct deck:

* **figure identity** (REVIEW) — one labelled measure carrying two different values across
  slides, the shape of the Wellworth 1,077/1,026 split. Labels are discovered from the deck
  rather than hardcoded to four words. REVIEW, not FAIL: proving two renderings are the same
  measure needs a builder-emitted sidecar, and inference should not block a ship.
* **period consistency** — FAIL on a span whose stated month count contradicts its own
  endpoints, and on a caption naming a month after the data snapshot. REVIEW on an earlier
  month, which is sometimes correct (carried-forward ICS financials).
* **source-note provenance** — FAIL on a data slide with no note or no Source line, and on a
  note naming a different client. That last is the CoastLife-defaults defect;
  `reference_leak_findings` reads slide text only, so a leak in the NOTES was invisible.

`pytest tests/` (277 tests) now runs as step 0 of `qa_all.py` and a failure fails the gate,
because a classifier regression that mis-buckets 18,000 accounts still produces a deck that
passes every layout rule. The fixture is a synthetic 800-row ODD carrying no member data.

### 2026-08-29 — one source for the palette, the slide primitives and the date phrases

Not a behavior change — every rendered colour and every rebuilt deck is byte-identical,
verified by rebuilding 1204 (49 slides, 38 chart images matching, 0 text differences). Logged
because it changes where these are sourced from.

The palette had been re-declared in seven files under four naming conventions, and five
different greys were in service as "the light grey"; it now lives in `build/brand.py`. The
slide primitives lived inside `product_mix_slide.py` — a module about one slide — where ICS
and MRPC could not reach them; they now live in `build/shapes.py`. `slide_geometry.py` moved
to `build/` and all three builders call it, so the next ICS or MRPC layout fix lands in the
contract instead of in one deck. Date phrasing derives from `build/periods.py`; a literal
month is still fine when it is the month being described, but spans and counts are no longer
hand-computed. ICS/MRPC client sheets resolve through `rpe_env.resolve_client_json` under
`Inputs/VIP Data/<PROGRAM>/<id>-<Name>/`, indexed by that folder's `manifest.json`, so a
fresh checkout on the CSI machine is no longer missing them. The loose
`data/<id>_<program>.json` stubs in the repo are searched LAST: the README there records
them as superseded by the per-client folders, and they are an older pull — 1705's stub is
the 2026-07-13 capture against the folder's 2026-07-15, so an earlier search silently
returned the stale one.

### 2026-08-28 — orange KPI tile label read grey

`_tile` drew every tile label in GREYB (#CFDBE8), the muted grey picked for a NAVY tile.
Against ORANGE that pairing carries almost no contrast and the label reads as grey text on
the fill — Aaron flagged it on FNB&T 1537's Reg E Opt-In by Branch slide.

The label is now white on an orange tile and unchanged on navy. Affects every slide with an
orange tile: Reg E Opt-In by Branch, Excluded Accounts, Product Mix & ARS Eligibility, and
the swipe-tier movement slides.

### 2026-08-28 — Reg E new-account branch caption claimed a staffing effect

The caption under the by-branch chart on "Reg E Opt-In — Opened in Last 12 Months" read
"Lower-staffed branches lag; higher-touch branches lead on new-account opt-in." The ODD
carries no staffing count and no measure of customer contact, so neither half of that claim
could be shown from the data behind the chart. It was template text, so it shipped on every
ARS deck regardless of what a client's branches actually did.

It now states what the chart plots — "Dashed line = <rate> overall." — matching the sibling
caption on the all-accounts slide. Both templates are corrected and the builder also sweeps
the old sentence, so a re-seeded reference deck cannot reintroduce it silently.

### 2026-08-28 — "ODD" no longer appears on a slide face

The Mailing Response Summary subtitle ended "Offers sent and responders counted from the
ODD", naming an internal system on a client-facing page. Removed from all three variants of
the line — first mailing, trailing window, all mailings — so it is gone regardless of how
many mailings a client has. Slide 13's speaker notes still name the workbook, the ODD
extract, its pull stamp and the period, so the figures stay auditable. Verified across all
nine 2026.08 decks; that subtitle was the only on-slide mention.

### 2026-08-28 — ICS financial detail is absent when the workbook predates the deck

Replaces the carry-forward rule. A monthly build carried the last ICS workbook's financial
sections forward and stamped the DECK's period on them: 1537 FNB&T and 1676 True Sky both
showed "PTD · August 2026" over an ICS Financial Summary built from a 2026.06 and a 2026.07
workbook respectively.

The builder now resolves the newest ICS workbook for the client from
`Inputs/ARS & MRPC Reports/` and compares its period to the deck's. On a mismatch the
workbook-driven sections are ABSENT rather than re-dated, reusing the referrals-only path —
the section divider drops to "Referrals" and the agenda stops naming account value, ROI and
financial results. Referrals, Referral Trend, Results by Branch and the education slides are
unaffected.

2026.08 effect: 1075, 1509 and 1539 have current workbooks and keep their financial detail;
1537 and 1676 lose it (ICS section 28 → 14 slides); 1549 had no workbook and was already
referrals-only. The referrals-only log banner no longer claims "no ICS workbook has landed"
in this case, which was untrue when one landed and is merely older.

### 2026-08-28 — empty age chart no longer drawn; last n= notation removed

The Age Profile slide already wrote the right sentence when DOB is absent — "Date of birth is
not carried in this client's data extract" — and then drew the chart anyway: an empty axis
with a row of twelve zeros. Missing data is stated and never zeroed; only the text half of
that rule was implemented. The plot is removed, the statement takes its place, and the
Selection line no longer promises an age mix that is not shown. 1537 FNB&T is the case: the
DOB column is present and blank on all 29,852 rows, which is a data-sourcing question for
CSI, not a pipeline defect. The PNG is still generated — skipping it would leave the
template's image19 in place and display the REFERENCE client's age chart.

Separately, the two Selection captions still carrying "n=" (New-Account Debit Adoption,
First-Year Closure) now state their population as a bare parenthetical like every other
Selection line.

### 2026-08-28 — Before vs After by Offer chart was unreadable at mailing volume

Every mailing month was labelled with an "(n=…)" second line beneath it. At fifteen mailings
(Sugar River 1038) the axis rendered as overlapping mush and the per-bar dollar labels
overprinted each other. The axis now labels every Nth mailing capped at 8 ticks, always
including the newest; "(n=…)" moves to the speaker notes as NU / TH per mailing, so the count
behind each bar stays auditable rather than dropped; per-bar dollar labels are drawn only
below 8 mailings, above which the y-axis carries the scale.

Affects the seven 2026.08 clients with more than 8 mailings: 1038, 1075, 1204, 1509, 1539,
1676, 1705. Slide 19's Mean chart needed nothing — its rotated labels handle fifteen. Same
shape as the excluded-accounts footnote bug: correct on Wellworth's single mailing, wrong at
volume, and passed by the gate because nothing overflows a box.

### 2026-08-28 — clients.md decides what gets built, not the presence of a data file

Program membership was inferred from whether input files happened to exist. That is how
CoastLife 1705 kept producing an ICS section after cancelling — their ICS data was still on
disk. `clients.md` now records intent and is the authority; leftover program data and a
2026.08 DCO file are explicitly not signals to build.

Confirmed by Aaron the same day: PointBank 1174 off the books entirely; Truliant FCU 1658 has
no RPE at all; CoastLife 1705 ICS cancelled with ARS continuing; Canandaigua 1437 ends
2026-10-31 with no further reviews; 1218, 1477 and 1502 MRPC-only; 1632, 1734 and 1738
ICS-only. Building the roster surfaced that 1204 FSB Michigan had 2026.08 inputs and no deck.

### 2026-08-28 — Excluded Accounts footnote is measured, not assumed

The footnote block sits at 6.05in with the logo band starting at 6.78in, so it holds two
lines. Which observations exist varies by client — 1549 has no Mail column at all, 1537 has
all three and estimated five lines, which failed the gate. Lines are now measured at the 16pt
floor `restyle_fonts` enforces and truncated to what fits; every observation still goes to
the speaker notes, so nothing is lost, only moved. The mail-funnel sentence is shortened to
one line.

The stale-caption check also stopped flagging derived pills. It compared any
template-identical dated text and caught "PTD · June 2026" on four of CoastLife's ICS slides,
correct at the time because ICS financials carried forward. It now covers caption prose over
40 characters, which still guards all 21 real template captions and exempts three pill forms
that each have their own swap guard.

### 2026-08-28 — responder counts now agree across slides

The same mailing reported different responder counts on different slides: Wellworth
1549's Jun 2026 drop read 1,077 on the mailing slides and 1,026 on Program Reach,
Depth of Engagement, Ranking and Sustained.

Cause: those four counted a HISTORICAL mailing's responders through the CURRENT
eligibility snapshot (`<latest> Elig`), which drops anyone who responded and has since
closed or gone ineligible — 51 accounts on Wellworth. Slides 18/19 already used the
personal cohort for exactly this reason (2026-08-27); the rest now match.

Affects every ARS deck. Reach, depth and ranking figures rise.

### 2026-08-28 — sustained rate measured after the response month

Sustained compared the extract's trailing 3 months against the ask, for every mailing.
For a recent mailing that window includes months from before the customer responded, so
it reported attrition that had not happened.

A response is recorded in the month AFTER the offer — Wellworth confirms it: 44% of the
Jun 2026 responders cleared their ask in June, 100% in July. The window now starts at
mailing+2. A mailing with no month after its response month reads 100% by definition and
is drawn grey with the caption saying attrition cannot appear yet.

### 2026-08-28 — before/after is mean only, split by offer

The median twin (slide 19) is replaced by the same mean, split into Non-User and
Threshold respondents. The two offers ask for different behaviour and pooling them hid
which one moved. Grouping keys on `<mon> Mail`, as mail_summary does.

A Non-User's baseline is near zero, so its percentage change is meaningless (Wellworth
computes +9,018% off $13); below a $25 baseline the narrative states dollars instead.

### 2026-08-28 — Stat Code fallback in the shared status classifier

`classify_status` only ever read `Stat Desc`. 1549 Wellworth populates `Stat Code`
(O/C/X) and leaves `Stat Desc` BLANK on every non-open account, so 18,274 of 50,218 rows
classified as "Other". `oddd_optimize.STAT_CODE_MAP` now maps O/A -> Open, C -> Closed,
X -> Charged Off (Aaron-confirmed); the description still wins when it carries text.

Affects the account-status mix on any client whose core fills the code, not the label.

### 2026-08-28 — take-rate-by-branch table showed months twice

`set_table` trimmed surplus template ROWS but not COLUMNS, so a client with fewer
activity months than the template's eleven kept the reference client's remaining
columns. Wellworth's table carried a second Apr/May/Jun and a second Cards/Elig/Take%
block from Union Financial. Columns are now trimmed to the data and the width
re-spread. The table also fills the slide (10 branches, was a fixed 6).

### 2026-08-28 — stale month captions

A dozen template captions carried the reference client's month and no swap ever reached
them, so a Jul 2026 extract shipped "Monthly debit spend (June 2026)", "opt-in status as
of June 2026" and "Jul 2023 - Jun 2026 (36 months)" on a client with five months of data.
Point-in-time phrases and series spans are now derived. `validate_deck` FAILs any dated
caption still byte-identical to the template's, scoped to the template's own reporting
month so a genuinely fixed window (the Kaplan-Meier cohort) is not flagged.

### 2026-08-28 — ICS branch goals pro-rated

Branch goals in the VIP export are ANNUAL, but a program that started partway through the
year has not had a year to hit them. Wellworth began in May; its Main branch read 24
against a 204 annual goal (12%), which reports the calendar rather than the branch. The
goal is now pro-rated to the months the program has run — Main reads 24 of 68 (35%), and
the top-8 total moves from 14% to 41%. Falls back to the annual goal when the run length
cannot be derived.

### 2026-08-28 — Reg E "no election" wording, and the ICS branch selection line

"No election means the customer was never asked" asserted something the data cannot
show, and put it on the branch. No election means only that we do not hold their
decision — they may well have been asked. Now reads "no election means the customer
hasn't given us one" (the exact phrase "didn't give us their decision" measures 12.30in
against 12.10in of box and wraps onto the tiles).

The selection line was removed from ICS "Results by Branch – Year to Date": with the
callouts and the pro-rating note it ran to ~20in of text in a 9.68in box, wrapped, and
its box overlapped the table above and the logo band below. Selection, branch counts and
the pro-rating basis are all in the notes.

### 2026-08-28 — combined deck split the ARS section at a fixed index

`assemble_combined` kept "the first 30 slides" ahead of the ICS section. That is only
right while the ARS deck is exactly 47 slides. Adding Excluded Accounts and Reg E by
Branch made it 49, and the boundary cut two slides early: "Reg E Opt-In by Account
Vintage" and "ARS Key Takeaways" were pushed AFTER the ICS section. The boundary now
resolves by TITLE ("ARS Key Takeaways") — CLAUDE.md: never by index. It printed a note
about the count mismatch and carried on regardless; it now states where the section ends.

Also: the combined agenda described the ICS section as "Referral trend, account value,
ROI & financial results" even for a referrals-only build that contains none of those.
Detected from the slides actually copied, not from a flag.

### 2026-08-28 — Reg E by Branch is new accounts, not the whole book

The table was built on every open personal card holder — a view dominated by decades of
legacy elections that says nothing about how branches are asking today. It now uses the
same trailing-12-month cohort and >=15 threshold as the new-account chart beside it, and
reconciles to `rege_new_pct`. The heading states the window ACTUALLY used: an extract
carrying fewer than twelve activity months yields a shorter one (Wellworth's is
Mar-Jul 2026), and "Last 12 Months" over five would be false.

### 2026-08-28 — referrals-only ICS agenda listed absent sections

The section divider correctly dropped to "Referrals", but the agenda still listed
Performance of ICS Accounts, ICS Revenue & Revenue Detail, ICS Financial Summary and
Comparisons — four sections a referrals-only build deliberately OMITS. Wellworth 1549
shipped that way. Rows are now removed, not blanked, for the same reason
`assemble_combined` removes them: an empty numbered row reads as a section that failed
to render. A full workbook-driven build still lists all eight.

### 2026-08-28 — client logo on the Agenda slide (ARS + ICS)

Placed in the right-hand third, which is empty: the agenda's own text reaches at most
8.80in (measured against the bundled TTFs at the 16pt floor), so a logo from 9.30in
clears it. Sourced from `Inputs/Logos/<clientid>.png` via `rpe_env.client_logo`, cropped
to its ink by `trim_logo` and fitted by `fit_box`. Absent logo = slide built without it.

`trim_logo` also re-encodes any file python-pptx cannot embed: 1539.png is really a
WEBP, which PIL opens happily and `add_picture` then refuses outright. MRPC has no
agenda slide, so it is unchanged.

### New slides — Excluded Accounts (ARS), Reg E Opt-In by Branch (ARS)

Excluded Accounts follows Product Mix: the eligibility waterfall (status -> product code
-> debit card, each account counted once) plus the per-client excluded product codes,
derived as those with no eligible account. $0 balance and address quality are reported as
observations, NOT exclusions — neither predicts the `Elig` flag.

Reg E Opt-In by Branch is the table companion to the two Reg E branch charts, carrying
opted-in / opted-out / no-election per branch.


### 2026-08-27 — tier response rate denominators (shipped)

Landed in `metrics_gen.mail_summary` (`metrics_gen.py:184-199`): `nu_sent` and
`th_sent` split on `<mon> Mail`, each group is rated against its own base, the
trailing total pools each group's own recipients rather than averaging the
per-mailing rates, and an unknown offer code raises the warning the PRD asked
for. Verified 2026-08-29. The description of the defect follows, kept because
the reasoning is the reason the fix looks the way it does.

`NU 5+` and `Threshold Met` on the ARS Mailing Response Summary divided by total
accounts mailed instead of by each offer group's own mailed count. They are
shares of the whole file, not response rates, and they sum exactly to the
overall response rate — which is the tell.

The fix, agreed 2026-08-26: each offer group is rated against its own mailed
base. NU responders over NU recipients; TH responders over TH-10 through TH-25
recipients combined; overall responders over total offers sent. The three no
longer sum, because the denominators differ.

The ODD already carries what's needed. `<mon> Mail` holds the offer strategy per
account (`NU`, `TH-10`, `TH-15`, `TH-20`, `TH-25`) — `metrics_gen.OFFER_GOAL`
maps exactly those five values, and the dot-plot code already reads it that way.
`mail_summary` simply never split on it.

Grouping keys on what was mailed (`<mon> Mail`), not on how the account
responded (`<mon> Resp`). Those should agree, but if they ever don't, keying on
the response tier puts a responder in a group whose denominator doesn't contain
them, and the rate can exceed 100%.

Touches `metrics_gen.mail_summary`, the six-value row unpack in
`build_ars_gen.py`, the slide-12 subtitle, and the stale comment block described
in the 2026-08-20 entry.

Affects: all nine 2026.08 ARS decks. None had been sent when this was found.

CoastLife 1705 v3 was patched by hand on 2026-08-26 as a stopgap, sourcing the
rates from the workbook rather than the ODD. The generator fix has since landed,
so v3 is superseded — regenerate CoastLife rather than referring to it.

---

## 2026-08-20

### Mailing response moved from the workbook to the ODD

Slide 12 read tier response percentages out of the workbook while slide 14
computed the latest mailer from the ODD, and the two disagreed on the same drop
— 16.3% vs 10.7% on Wellworth 1549. Both now use one definition: offers sent =
personal accounts carrying a `<mon> Mail` value; responders = those whose
`<mon> Resp` reached a goal tier.

The rationale recorded in `build_ars_gen.py` states the workbook's denominator
is not the mailed population. That reasoning does not hold for every client —
CoastLife's workbook denominators reconstruct the mailed population exactly
(2,015 NU + 2,756 TH = 4,771 offers sent, Jun 2026). Wellworth has a single
mailing and no lift matrix, so it was a thin case to generalize from.

Single-sourcing to the ODD was still correct. The denominator was the separate
bug, unfixed here, and carried forward into every deck built after this date.

**Update the comment block in `build_ars_gen.py` when the Unreleased fix lands.**
It currently argues for behavior we are changing.

### Other fixes the same day

- Title-slide and PTD-pill months were never swapped; every 2026.08 ARS deck
  shipped the template's "July 2026" and "PTD · June 2026".
- Business take-rate branch chart had no bar cap while sharing the personal
  chart's geometry — 19 bars on 1549, 37 on 1075, x labels unreadable.
- The 2:1 profitability sentence was a template literal, so a client below the
  threshold shipped "0.2 : 1 is well above the 2 : 1 threshold".
- Mailing Response Summary carried the reference client's rows below a short
  client's data; `set_table(trim=True)` now drops them.

---

## 2026-07-25

- Slide resolution moved from indices to titles (`SB()`), which raises instead
  of silently no-opping. Index access is how the Appendix swaps went stale.
- Swap gate added: any find-string matching nothing fails the build. A miss
  would ship the reference client's numbers.
