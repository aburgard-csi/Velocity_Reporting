# Operations: the daily source watch

The full account behind the **Daily source watch** section of CLAUDE.md: the incidents behind each rule, the registration history and the watchdog's record. CLAUDE.md carries the rules that matter when editing this code; this file keeps the history. Moved here verbatim on 2026-10-06 (prompt audit, finding 12); the heading below is the original one.

### Daily source watch

```
python scripts/watch_sources.py [--notify] [--dry-run] [--period 2026.09 ...]
python scripts/watch_sources.py --check-stale     # has the daily watch been running?
powershell -ExecutionPolicy Bypass -File scripts\register_watch_task.ps1 \
        [-Time 08:00] [-Repo <checkout>] [-RetryHours 0] [-Unregister]
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
`source_watch_latest.md` (the latest report), `source_watch_runs.json` (the run
record — see below). The first run is a baseline and reports counts, not news.
**The scan's report, log block and inventory are saved BEFORE the copy and the steps
after it (Aaron, 2026-09-21)** — `save_report` is called twice, and the report is
rewritten whole when the steps finish. A run killed part way (the 08:00 runs of
2026-09-18 through -20 were, on a slow share, under the old 30-minute execution
limit) leaves its scan rather than nothing at all, which is what the watchdog reads.
**The execution limit is 50 minutes** (`register_watch_task.ps1`, Aaron, 2026-09-21) —
this file said "2 hours" until 2026-10-05, and the script was right. The copy runs
after `record_finish`, **small files first: every DCO, workbook and analysis before any
ODD extract, and the extracts smallest first** (`watch_sources._copy_order`, Aaron,
2026-10-05). It went by kind until then — DCOs, ODD extracts, workbooks — and at what the
share gave that morning (~0.3 MB/s beside a launcher build; ~3 MB/s quiet) a month's
extracts (~2 GB) put the limit inside the third extract with the seven 1 MB workbooks
still to copy, and the next fire would have started the same list in the same order. An
extract a cut-short run does not reach is copied the next morning; a workbook no longer
waits behind it. **Off VPN it exits 2 and leaves the saved inventory alone** — saving an empty
one would make every file "new" the next morning.

**A run that never happened writes nothing, so the check for it lives OUTSIDE the
watch (2026-09-11).** On 09-09, -10 and -11 the 08:00 task was created by the
scheduler and left SUSPENDED — zero CPU, no modules loaded, the interpreter never
initialized — then killed at the execution limit. No log line, no report, no
toast, and nothing in the pipeline knew for three days. A heartbeat inside the
script could not have caught it; only something else asking could. So:

- `watch_sources.run_health()` reads `source_watch_runs.json` and answers
  `ok` / `stale` / `never`, measuring age from the last FINISH — a killed run
  leaves a start with no finish, a run that never starts leaves neither.
  **Outcome is ignored**: a run that found the shares down still RAN.
- **`refresh_performance_dashboard.py` prints it every morning at 08:30**, on a
  different scheduler, which is the point. The delivery dashboard banners it too.
- `--check-stale` asks from anywhere and **scans nothing**, so it answers off VPN.
- **The trigger fires ONCE, at 08:00, with `-WakeToRun` (Aaron, 2026-09-25).** It
  used to repeat hourly for four hours, with `--once-daily` making a repeat that
  followed a run which **reached the shares** exit at once. `-RetryHours 4` puts
  that window back. Know what one fire gives up: the watchdog still recovers a
  fire Windows created suspended, but a morning off the VPN now gets no copy at
  all — the run goes, reports the shares unreachable and finishes, so there is
  nothing stuck to recover and no later fire to go and look. Run it by hand once
  the VPN is up. `--once-daily` is still passed, so a hand-run after a successful
  one exits at once.

Do not "simplify" this by having the watch check its own health. That is the one
thing it cannot do.

`register_watch_task.ps1` schedules it as the Windows task **"RPE Source Watch"**,
daily at 08:00 as the logged-on user (the share needs those credentials and the
toast needs a desktop), catching up a missed run when the laptop wakes.
Registered on this machine 2026-09-08, re-registered 2026-09-11 with the retry
window, `-WakeToRun` and a 20-minute limit (short enough that a stuck fire is
cleared before the next is due, or `MultipleInstances IgnoreNew` drops it),
re-registered 2026-09-21 with the 50-minute limit, and re-registered 2026-09-25 with
**no retry window at all** — one fire a morning. **The file-get runs ONCE a day, at
08:00, and no more (Aaron, 2026-10-05: "if it's running more than that it's too
much").** Do not start a hand-run beside it: two copiers writing the same `Inputs/`
folder was how the 2026-10-05 duplicate came about. The one sanctioned second fire
is the watchdog's retry, and only on a morning the 08:00 fire never executed.
**`-Repo` points it at a checkout other than the one the script lives in** — a
worktree has no `.venv` and no `.env` and cannot host the task. The script omits
`--once-daily` when the target checkout does not know the flag, because it is
routinely newer than the code it registers and an unrecognised argument would
make every fire exit without checking anything. `--notify` raises a Windows toast only when
there is news or the shares were unreachable; a quiet day is silent.

**The daily run also files CSM Sheila's issue reports (Aaron, 2026-10-05).** With `--issues`,
which the scheduled task passes, `issue_reports.sync()` files every report queued on the share
and refreshes the issue list Sheila's **Feedback** tab reads. It runs with the MAIL step, after
the share results are saved, for the same reason: it reaches off the machine. gh lives on this
machine only — which is why the sync is here and not in Sheila, where a token would sit on the
share — and a morning with no gh or no internet leaves the reports queued for tomorrow.

**The daily run also reads the MAILBOX (Aaron, 2026-09-09).** Some inputs never land on a
share: **MRPC and CashPlease reports from Bradford Sanders**, **the per-client CashPlease
marketing emails from him** (`<id>_<Client>_Loan_Marketing_Emails.xlsx`, their own kind since
2026-09-21 — eight of them had been reported and left where they were, because a name with no
period reads as unclassifiable), and **ICS workbooks from Matt Milliman**. `--mail`, which the
scheduled task passes, takes them from Outlook via `scripts/mail_sources.py` and files them by
kind alongside everything else.

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
  (`watch_sources.mail_step`, `MAIL_TIMEOUT` = 10 min) with its output in FILES, not
  pipes, and a timeout kills the whole process tree under it (`_kill_tree`; 2026-10-07,
  after the relaunch left under the child held the pipe and the run hung for hours) and
  is reported as "TIMED OUT", not fatal; and `mail_sources._outlook()` attaches to the running Outlook
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

**The share refuses some zipped extracts, silently (2026-10-13, 1815 FedChoice).** The log
read `1815_ODDD.zip FAILED: size mismatch after copy (13838993 vs 13410387)` on 10-07, 10-08
and 10-13 while `Inputs/ODDD/1815_ODDD.zip` stayed September's (13.8 MB; October's is 13.4 MB).
Probed by hand: a `.part` file, a plain zip and both raw CSVs written to `Inputs/ODDD` survive;
a zip holding the ODD CSV alone survives; the full extract — the ODD CSV plus the data team's
`…_monthlytrans.csv` — vanishes the instant it is written, under any name, and `shutil.copy2`
returns without an error. So `os.replace` of the vanished `.part` failed, the fallback write
left the old file in place, and the size check reported the old file's size. 1147's extract,
packed with a different kind of transaction file, is held, so the refusal is by content — the
same agent that refuses four `Inputs/Txn Files` zips. `apply_copies` now falls back to
`_land_odd_member_only`: the ODD member(s) written into a new zip with their original entries
(the pull stamp `deck_status.odd_stamp_period` reads is unchanged), `reduced` on the record,
and the report line names what was left out. The reduced copy's write time is newer than the
source, so the next morning's "differs" is left alone by the changed-on-purpose guard. October's
1815 extract was landed this way by hand at 15:05 (2.5 MB, stamp 2026.10).

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
Watchdog"**, from 08:20 and **every 30 minutes for four hours** (Aaron, 2026-09-21), so a
fire created suspended at 09:00 or 10:00 is cleared while the morning still matters. It asks
`watch_sources.py --check-today` — has a run REACHED THE SHARES today, from the run record —
rather than reading the report's age: on 2026-09-21 the 08:00 report was 52 minutes old and
fresh while the 09:01 fire sat suspended and that morning's copy was never going to happen.
(An older checkout without the flag falls back to the report's age.) Not a background thread of the main task — if whatever suspends
the main process can suspend it, a thread living inside that same process is exactly
as stuck; a second, independently-triggered task is the only vantage point actually
outside the failure. Each firing: if `source_watch_latest.md` is already fresh
(within 3 hours), it exits silently — the common case, every healthy morning. Otherwise
it looks for a `watch_sources.py` process matching the suspended signature (near-zero
CPU, near-zero handles, old enough — 4+ minutes — that a healthy run would have
finished), kills the whole process tree, and retries the main task; up to two
kill-and-retry cycles before giving up and logging for a human. Every attempt is
appended to `Build Artifacts/source_watch_watchdog.log`. Registered on this machine
2026-09-11, verified end-to-end via `Start-ScheduledTask`. **The kill-and-retry path
has now run for real (2026-10-05).** At 11:31 it found the 08:00 fires of 2026-10-01
and 2026-10-03 still present and suspended — ages 4.1 and 1.7 days, CPU 0, handles 0 —
killed both, retried the task, and the retry reached the shares three minutes later and
started on the 65 files that had landed since the last real fetch. Without it that day
would have had no fetch at all, which is why it stays (Aaron, 2026-10-05: "keep the
watchdog"). Three things that day and the next showed; two are now explained and fixed:

- **The scheduler's execution limit does not clear a suspended fire.** Task Scheduler
  reported the 2026-10-01 fire terminated (`0x41306`) at 08:50, and the process was
  still there four days later. Only the watchdog's kill removed it. Still open.
- **The detection missed a lone process.** On 2026-10-01 the watchdog fired nine times
  and reported "no suspended process found" about the same process it found and killed
  on 10-05. Explained 2026-10-07: `Find-StuckWatchProcesses` returned its list bare, and
  Windows PowerShell 5.1 unrolls one result to a scalar with no `.Count`, so a single
  stuck process was never counted — every "found" line in the log was a pair. Fixed
  (`, $stuck` and `@()` at the call site; `tests/test_watchdog_single_process.py`).
  **That fix over-corrected** (2026-10-08 and 2026-10-12): `,$stuck` met the `@()` at the
  call site and the result was wrapped twice, so NO process came back as one element, an
  empty array. Attempts 2 and 3 of each of those mornings logged "found 1 stuck
  process(es)", then `PID  (parent ): age s, CPU , handles  --` with every field blank,
  killed nothing and fired the task again while the retry they had just started was
  running. Fixed 2026-10-13 ("fix the watchdog log bug too"): the function writes each
  stuck process to the pipeline as its own object and the callers keep their `@()`, the
  one shape that counts right for none, one and several. The tests now call it the way the
  script does and pin the empty case, the per-process fields and the logged line.
- **The run that reached the shares then hung in its mail step** (13:49 on 10-05, until
  killed by hand that evening; again from 08:16 on 10-06). The endpoint agent relaunches
  every python start as a child with the same command line; a relaunch it leaves suspended
  inherits the mail child's output pipe; `subprocess.run(timeout=)` killed only the child
  and then read the pipe to an end that never came. Two consequences: the hung run looked
  healthy to the watchdog (73 s of CPU, 161 handles) and, the task being `MultipleInstances
  IgnoreNew`, the next 08:00 fire was dropped. Fixed 2026-10-07 (Aaron: "do both"):
  `mail_step` hands the child FILES, not pipes, and on a timeout kills the whole tree
  (`_kill_tree`, `taskkill /T`); the watchdog treats any `watch_sources.py` process older
  than `MaxAgeSecondsAlive` (3 h) as stuck whatever its counters, and clears one even on a
  morning whose run reached the shares, so it cannot block the next fire.

A morning that logs "needs a human look" IS the human look: check for a `pythonw.exe`
with 0 CPU and 0 handles, or one from yesterday, by hand.

`register_watch_task.ps1` had drifted from the live task it describes — the
registered task already carried `--mail` (added when the mailbox step landed,
2026-09-09) but the checked-in script's `Argument` string did not, so re-running it
would have silently dropped mail reading. Fixed 2026-09-11; both now agree.
