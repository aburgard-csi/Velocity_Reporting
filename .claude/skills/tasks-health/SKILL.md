---
name: tasks-health
description: Check the morning automation on Aaron's machine - the RPE Source Watch (08:00), its Watchdog (08:10) and the RPE ILS Analysis Landing (08:20) scheduled tasks, the tasks checkout they run from, and their latest reports. Use when asked whether the morning tasks ran, why inputs did not land, after a release or a clock change, or for a health check of the scheduled tasks. Read-only; any fix needs Aaron's yes.
---

# Morning tasks health

Three Windows scheduled tasks copy the day's inputs. They run from their own checkout, `C:\Projects\RPE-Tasks`, which a
release moves to the released commit (merge-and-release skill). Everything here READS; re-registering a task or moving
the checkout is a fix and needs Aaron's yes (**STOP** at step 5). The incidents behind each rule are in
`docs/OPERATIONS-source-watch.md`; do not restate them, read it when a check fails.

## 1. The tasks

| Task | When (local) | Registered by |
| --- | --- | --- |
| RPE Source Watch | 08:00 | `scripts/register_watch_task.ps1` |
| RPE Source Watch Watchdog | 08:10 | `scripts/register_watchdog_task.ps1` |
| RPE ILS Analysis Landing | 08:20 | `scripts/register_ils_landing_task.ps1` |

```
foreach ($n in 'RPE Source Watch', 'RPE Source Watch Watchdog', 'RPE ILS Analysis Landing') {
    $t = Get-ScheduledTask -TaskName $n; $i = Get-ScheduledTaskInfo -TaskName $n
    [pscustomobject]@{ Task = $n; State = $t.State; Start = $t.Triggers.StartBoundary; Next = $i.NextRunTime
        Last = $i.LastRunTime; Result = $i.LastTaskResult; Exec = $t.Actions.Execute
        Args = $t.Actions.Arguments; Dir = $t.Actions.WorkingDirectory }
}
```

Check, for each:
- **NextRunTime reads 08:00 / 08:10 / 08:20 local.** One hour off is clock-change drift (below).
- **Every action points at `C:\Projects\RPE-Tasks`** (Execute, Arguments or WorkingDirectory), never at
  `C:\Projects\RetailPerformanceEngine` or a worktree.
- **LastRunTime is this morning** and **LastTaskResult** is 0. 267009 (0x41301) means still running, 267011 (0x41303)
  never run; anything else, read the reports in step 3.
- A `watch_sources.py` (pythonw) process older than three hours is stuck whatever the task says (OPERATIONS doc).

**Clock-change drift.** A task whose trigger was registered with a fixed UTC offset (`StartBoundary` ending in e.g.
`-04:00`) drifts an hour at each daylight-saving change. In November 2026 the watch was firing at 07:00 and the watchdog at
07:10. NextRunTime in local time is the check, not the StartBoundary text.

## 2. The tasks checkout

```
$tc = 'C:\Projects\RPE-Tasks'
Get-Content '\\PADMIS105\Velocity_company\CSM_Reporting\Tools\RPE\RELEASE.txt'     # "released ... at <sha> (on origin/main, clean)"
git -C $tc rev-parse --short HEAD                                                     # must equal that <sha>
git -C $tc status --porcelain                                                         # must be empty
Get-Item "$tc\.venv" | Select-Object LinkType, Target                                # a Junction to the real checkout's .venv
Test-Path "$tc\.venv\Scripts\python.exe"
fsutil hardlink list "$tc\.env"                                                       # two names: this one and the real checkout's .env
Select-String -Path "$tc\.env" -Pattern '^\s*(RPE_TASKS_CHECKOUT|RPE_SRC_ILS_SCHEDULE)\s*='
```

- `RELEASE.txt` carries a SHORT sha; compare it with `rev-parse --short` (if the lengths differ, compare prefixes).
- HEAD behind the release means the release's "move the tasks checkout" step did not run (the output said "left alone"
  or "not set") or a release came from an old script copy.
- A non-empty `status --porcelain` means someone edited files there; nothing should. Report it, do not clean it.
- A broken junction or a `.env` with one link name means the tasks run without the venv or with a stale copy of the
  settings. Both `RPE_TASKS_CHECKOUT` and `RPE_SRC_ILS_SCHEDULE` must be set.

## 3. What the runs say

```
$py = 'C:\Projects\RPE-Tasks\.venv\Scripts\python.exe'
& $py C:\Projects\RPE-Tasks\scripts\watch_sources.py --check-stale    # ok / stale / never, by last FINISH; answers off the VPN
& $py C:\Projects\RPE-Tasks\scripts\watch_sources.py --check-today    # exit 0 if a run reached the shares today, 1 if not
```

Then read the newest reports in `<RPE_DATA_ROOT>/Build Artifacts/`:

- `source_watch_latest.md`: this morning's scan (what landed, what was copied, mail, prune).
- `source_watch_watchdog.log`: the tail; "needs a human look" is the human look.
- `ils_analysis/landing_latest.md`: the ILS analysis landing's report.

Check each report's date is today. **Off the VPN the share reads "unknown", not broken**: the watch exits 2 and leaves
its inventory alone, so say "off VPN, not checked" rather than reporting missing inputs.

## 4. Report

One short table: each task (next run, last run, result, checkout path OK), the checkout (HEAD vs release, clean, junction,
hard link, the two settings), and each report (date, headline). Name each problem and the fix it needs.

## 5. STOP: fixes need Aaron's yes

Ask before any of these, saying what it changes:

- **Re-register a task** (drift, wrong checkout, missing task), always from the tasks checkout's own copy:
  ```
  powershell -ExecutionPolicy Bypass -File C:\Projects\RPE-Tasks\scripts\register_watch_task.ps1 -Repo C:\Projects\RPE-Tasks
  powershell -ExecutionPolicy Bypass -File C:\Projects\RPE-Tasks\scripts\register_watchdog_task.ps1
  powershell -ExecutionPolicy Bypass -File C:\Projects\RPE-Tasks\scripts\register_ils_landing_task.ps1 -Repo C:\Projects\RPE-Tasks
  ```
  Then re-run step 1: NextRunTime must read 08:00 / 08:10 / 08:20 local.
- **Move the tasks checkout** to the released commit: the steps in the merge-and-release skill (section 2), only when
  `status --porcelain` is empty.
- Starting a task by hand (`Start-ScheduledTask`) is also a run of the copy step: not beside a run already going (two copiers
  writing `Inputs/` made a duplicate), and only when asked.

## Gotchas

- **`register_watchdog_task.ps1` has no `-Repo` parameter.** It registers the checkout it lives in, so run the copy inside
  `C:\Projects\RPE-Tasks`. It has no `[CmdletBinding()]`, so a `-Repo` passed to it is silently ignored rather than refused.
  The watch and ILS landing scripts do take `-Repo`; without it they register their own checkout.
- **A worktree cannot host a task**: it has no `.venv` or `.env`. The tasks checkout borrows both by junction and hard link.
- **The watch runs once a day** (Aaron, 2026-10-05); the watchdog's retry is the one sanctioned second fire. Do not add retries.
- **Health is checked from outside the watch.** A run that never executed writes nothing; do not "simplify" this by having
  the watch report on itself.
- **Never register or change a task without Aaron's yes**, never from a working checkout, and never edit files in the
  tasks checkout.
