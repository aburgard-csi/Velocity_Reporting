# Inputs/ILS Analysis: naming and organization

Aaron, 2026-11-06: "clean up the file names in Inputs\ILS Analysis and create a naming convention and organization system for
those files going forward." This is the convention. `scripts/ils_analysis_inputs.py` applies it (and `target()` in it is the one
place the rule lives); `tests/test_ils_analysis_inputs.py` pins it.

## What the folder is

A copy of the small files from the ILS client analysis share (`\\ilsdbsrvr2.csi.corp\ClientAnalysis`): each client's dated data pulls,
with the analysis workbooks the analysts built beside the extracts. **The originals on that share are the backup**, as everywhere
in `Inputs/`; nothing here is the only copy. Nothing in the pipeline's builders reads this folder yet. The ILS Program Analysis
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

Many of the files here are small copies (the landing step only takes files under 2 MB), so a file named for a kind is that kind's
extract as it was landed, not a promise that it is the whole extract. The size is in the plan list.

## Analysis files

Workbooks, pivots, chart tables, the numbered `00_MASTER_ANALYSIS` / `204_Pcomp3` / `300_branch_report` family, matrix parameter
workbooks, peer data: everything that is not an extract goes under the pull's `analysis/` with **its own name unchanged**, and
with any subfolder it was in (`analysis/PEER/p01_cu.csv`). They are the analysts' documents, not ours to rename, and several are
referred to by name in decks. A matrix parameters workbook is a client document: its home is the SharePoint client folder, not
here.

## Going forward

* **New pulls** are filed by the landing step with the same function: `land_ils_analysis.py` should call
  `ils_analysis_inputs.target(client, rel, pull)` for each file rather than copy the share's path, and treat a file whose target
  exists at the same size as already landed. (Until it does, run `ils_analysis_inputs.py` after a landing.)
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
