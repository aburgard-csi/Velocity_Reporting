# Inputs/ILS Analysis: naming and organization

Aaron, 2026-11-06: "clean up the file names in Inputs\ILS Analysis and create a naming convention and organization system for
those files going forward." This is the convention. `scripts/ils_analysis_inputs.py` applies it (and `target()` in it is the one
place the rule lives); `tests/test_ils_analysis_inputs.py` pins it.

## What the folder is

A copy of the small files from the ILS client analysis share (`\\ilsdbsrvr2.csi.corp\ClientAnalysis`): each client's dated data pulls,
with the analysis workbooks the analysts built beside the extracts, and (since 2026-11-24) the whole newest pull of each client on
the analysts' review schedule, zipped (see **Landing the scheduled clients' pulls**). **The originals on that share are the
backup**, as everywhere in `Inputs/`; nothing here is the only copy. The ILS Program Analysis
builder (`build/ils_analysis`) reads a pull from a folder you point it at (`--from-folder`), finding the extracts by file name.

## The layout

```
Inputs/ILS Analysis/
  ILS and DS Client Review Summary.xlsx          the one file that belongs to no client
  <client id>/                                   the four-digit client number, nothing else
    <yyyymmdd>/                                  one folder per data pull, dated the day it was run
      <id>_<kind>_<yyyymmdd>.<ext>               the pull's extracts
      analysis/                                  everything else from that pull, with its name as it was
    _unplaced/                                   a folder that names no date; set aside, never guessed at
```

* **One folder per pull, named by the pull's date.** `20260810`, never `DataPull_202608`, `Data Pull 2017-07-13` or `2015_08`.
  A legacy folder that recorded only a month keeps the month, `yyyymm` (`201508`); the tool does not invent a day. A month folder
  that holds one dated pull inside it (`DataPull_202304/DataPull_20230413/`) takes the inner day.
* **Client folder = the number.** The same as `Inputs/ILS PGL/<id>/` and `Inputs/Txn Files/<id>/`. The client's name is in
  `Client CSM List.csv`; it is not repeated in a folder name that would go stale on a rename.
* **No folder is nested twice.** `DataPull_20250924/DataPull_20250924/file` is `20250924/file`.

## Extract names

`<id>_<kind>_<yyyymmdd>.<ext>`: the client number first so a file that is copied out of its folder still says whose it is, the kind
in lower case with no spaces, the date last so a client's pulls sort by kind and then by age. The extension is lower case.
The date is the one the file's own name carried (`DataOps_20260811.csv` in the `20260810` folder stays `..._20260811.csv`);
a file that carried none takes its pull folder's date.

| kind | what it is | names it replaces (a sample) |
| --- | --- | --- |
| `zaccounts` | the account extract (ZAccounts) | `zaccounts_20261012.csv` |
| `ztrend` | the notice extract (ZTrend) | `zTrend_...`, `Data Ops Z Trend_...`, `1720_ztrend_...` |
| `debitdeclines` | debit declines | `DebitDecline_...`, `debit_declines.csv` |
| `refundhistory` | refunds | `RefundHistory_...`, `Refunds_...`, `Z_Trend Pull Refund_...` |
| `adjustments` | fee adjustments | `Adjustments_...`, `adjustments_...`, `Adjustment_...` |
| `dataops` | the Data Ops notice pull | `DataOps_...`, `Data_Ops_...`, `Dataops_...` |
| `cashpleaseloans` | CashPlease loans | `cashplease_loans_...`, `CPLoans.csv` |
| `loanhistory` | loan history | `Pull_Loan_History_...` |
| `matrixval`, `dbic` | the matrix validation and DBIC dumps (`.txt`) | |
| `account_types`, `branches`, `institutions`, `returned_deposits`, `mobile_deposits`, `overdraft_history` | the small tables of the older split ZAccounts query | |

The first six are the names `ils_review.cli.find_inputs` globs for (`*zaccounts*.csv`, `*ztrend*.csv`, `*matrixval*.txt`,
`*dbic*.txt`, `*debitdecline*.csv`, `*refundhistory*.csv`), so a folder laid out this way can be handed to the builder as it
stands. Only `.csv` and `.txt` files are extracts; a workbook is an analysis file whatever its name says.

A few pull folders use short names instead (2026-11-24). These are matched on the WHOLE name (dates, separators and a leading
client number taken out), never as part of a longer one (`ils_analysis_inputs.ALIASES`): `zaccount` and `za` are `zaccounts`,
`zt` is `ztrend`, `dd` and `declines` are `debitdeclines`, and `matrix` is `matrixval`. `za` / `zt` / `dd` are the analysis
team's Data Validation output, which the builder already accepts in place of the raw extract.

Many of the older files here are small copies (the first landing only took files under 2 MB), so a raw file named for a kind
is that kind's extract as it was landed, not a promise that it is the whole extract. The size is in the plan list. The zipped
extracts landed for scheduled clients are whole.

## Analysis files

Workbooks, pivots, chart tables, the numbered `00_MASTER_ANALYSIS` / `204_Pcomp3` / `300_branch_report` family, matrix parameter
workbooks, peer data: everything that is not an extract goes under the pull's `analysis/` with **its own name unchanged**, and
with any subfolder it was in (`analysis/PEER/p01_cu.csv`). They are the analysts' documents, not ours to rename, and several are
referred to by name in decks. A matrix parameters workbook is a client document: its home is the SharePoint client folder, not
here.

## Landing the scheduled clients' pulls (Aaron, 2026-11-24)

CSM Sheila builds the ILS analysis review from this folder, so the newest pull of each client on the analysts' review
schedule is copied here by `scripts/land_ils_analysis.py`, its own step (a hand run, or the "RPE ILS Analysis Landing" task
that `scripts/register_ils_landing_task.ps1` registers, daily at 08:20). `python scripts/land_ils_analysis.py` prints the plan
and writes nothing; `--apply` lands it; `--client <id>` limits it; `--current-only` leaves out the clients whose newest pull is
an earlier review's.

* **Sources, read only.** The schedule is `deck_status.SRC_ILS_SCHEDULE` (`RPE_SRC_ILS_SCHEDULE`, from the environment or
  the repo's `.env`), the share's `current_scheduled_analysis.csv` by default, or the analysts' live `.xlsx` (the same column
  names; only `fi_id`, `status` and `review_date` are required). **The share's `.csv` was last written in October 2022**, so
  on it no review is upcoming; set `RPE_SRC_ILS_SCHEDULE` in `.env` to this machine's synced copy of the live workbook
  (`.env.example` shows where). A schedule more than 30 days old is warned about on every run. The pulls are on `deck_status.SRC_ILS_ANALYSIS` (`RPE_SRC_ILS_ANALYSIS`), the share
  `build/ils_analysis/ils_review/peer_pull.py` reads (a test pins the two names equal). A client number that matches two client
  folders there is reported and left, never guessed.
* **Which clients.** A schedule row whose review date is from today to 60 days ahead, or whose status says OVERDUE, and not
  cancelled: the analysts' weekly scheduling email selects the same way. One row per client, its earliest upcoming review, else
  its latest overdue one (`ils_analysis_landed.in_scope`).
* **Which pull.** The newest pull folder or zip (a name with "data pull" in it) that holds an extract: its own files, a pull zip
  or pull folder inside it, or a zip's members. Its date is `pull_date()`'s: the folder's own day, else the day of the zip or
  folder inside it, else the month (`DataPull_202611` holding undated files lands as `202611`). Other folders inside a pull
  (`uncleaned data`) are not read.
* **What lands.** Every extract, under its `target()` name, **zipped**: `<id>/<pull>/<id>_<kind>_<date>.<ext>.zip`, one member
  of the canonical name. The analysts' .pptm, .pbix and workbooks are their outputs and are not copied; a .csv / .txt the
  convention does not know (`DataIntegrity_...txt`, a misspelled `ztend_...csv`) is listed in the plan, not landed or guessed.
  Two files that take one name (`Zaccounts.csv` and `za.csv`) land once, the export's own name first.
* **Safely.** Each zip is written as `.zip.part`, read back (member name, size and CRC against the source) and renamed; its
  presence is checked again. A zip the share removes or empties (its security agent has done this to zips before) is landed raw
  instead, checked the same way. A file on hand at the same size, zipped or raw, is skipped; one at another size is reported
  and never overwritten. Every zip a run landed is looked at again at the end of the run, and one gone by then is landed raw.
* **In what order.** Clients whose pull is current first, then smallest files first. A 45-minute budget stops between files
  and the next run carries on; a file that would overrun what is left of the budget waits, and one too large for any budgeted
  run is reported and left for a hand run with a larger `--budget-minutes`. `pulls.json` is written before the first file
  and after the last, and each landing is logged as it is made, so a run cut off at the task's limit still leaves a record.
* **For Sheila.** `_schedule/current_scheduled_analysis.csv` is the schedule, only the columns these rules read (never the
  contacts or notes the live workbook carries), replaced only when its content changes; `_schedule/schedule_read.json` records
  each read. `_schedule/pulls.json` holds, per scheduled client, the review, the newest pull, the kinds on the share and the
  kinds landed (never a kind whose file on hand differs from the share's: those are listed under `differs`), the required
  kinds missing (ZAccounts and ZTrend), the names not recognised, and **whether the pull is current**. A run limited by
  `--client` keeps the other clients' entries. Each landing is logged in `Build Artifacts/ils_analysis/landings.json`; an `--apply` run's report is
  `landing_latest.md` beside it.
* **A current pull** is one run no more than 60 days before the review date, or after it. Calibrated on the schedule's own
  history: of about 300 reviews held since June 2025, the newest pull before the review came a median of 22 days earlier, 48
  days at the 90th percentile and 56 at the 95th. A month-only pull counts from the 1st. The schedule's status is shown with
  the reason but does not decide it. A stale pull is landed (it does no harm) and marked `current: false`; the review waits for
  the new pull.
* **Reading it back.** `scripts/ils_analysis_landed.py`: `scheduled()`, `pulls_status()`, `landed_files(client, pull)` (raw or
  zipped; raw first) and `stage(client, pull, dest)`, which writes the extracts unzipped under their canonical names for
  `python -m ils_review.cli --from-folder <dest>`.
* **The morning watch** (`watch_sources.py --ils-analysis`) lists each scheduled client's newest pull by name, reports the
  ones new since its last listing (`Build Artifacts/ils_analysis/watch_state.json`) and the clients still waiting for a
  current pull. It copies nothing, and that server being down is reported without failing the watch.

## Going forward

* **New pulls** of scheduled clients are filed by `land_ils_analysis.py` with the same function (`target()` per file); a
  file whose target is on hand at the same size counts as landed. A landed `<name>.zip` is filed as its member is, so
  `ils_analysis_inputs.py` leaves it where it is.
* **A hand-landed pull** goes in a `<yyyymmdd>` folder under the client number, named as above; run
  `python scripts/ils_analysis_inputs.py --client <id>` to check it. It prints the plan and moves nothing without `--apply`.
* **Never rename by hand** inside a pull folder to anything but the convention: the tool is idempotent, so a folder that already
  follows it produces an empty plan.

## Safety

* The tool never deletes a file, never overwrites one (`os.rename` refuses an existing target) and never moves a file it cannot
  place. A collision (two files that would take one name, or a name already there) is reported and both are left.
* Before the first move a list of every move is written to `Build Artifacts/ils_analysis_inputs/renames-<stamp>.csv`;
  `--undo <that file>` puts every file back and removes the folders the undo empties.
* A folder is removed only when the moves left it empty (`os.rmdir`).
