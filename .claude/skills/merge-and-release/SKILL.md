---
name: merge-and-release
description: Merge pull requests on aburgard-csi/Velocity_Reporting once CI passes and release CSM Sheila (the launcher) to the share. Use when Aaron says "merge #N once CI passes", "merge and release", "release the builder/launcher", or when a PR has a merge conflict or a failing check to fix. Covers the CHANGELOG conflict, CI-style test runs, the flaky test, the main-branch check before a release, and the backup tag.
---

# Merge and release

A merge changes `main`; a release changes what every CSM's PC runs. **Do neither until Aaron says so in this
conversation, and never extend one approval to the next change.** "Merge #N once CI passes" is a merge. A release needs
the word "release" (or "release the builder/launcher"). Opening a PR, pushing a branch and fixing a conflict
on it are fine without asking. Never rebase, never force-push, never use `-FromWorkingTree` or `-Force` on the release.

## 1. Merge a PR

1. **Wait for CI**: `gh pr checks <N> --repo aburgard-csi/Velocity_Reporting --watch --interval 30` (the `pytest` job, about 5 minutes).
   Check `gh pr view <N> --json mergeable,state,headRefOid` first: an Auto-fix event can name an OLD head, so compare it with the
   current `headRefOid` before acting. A conflict or failure on a head you already replaced needs nothing.
2. **If it conflicts**, fix it on the PR's own branch (work in a scratch worktree, never the main checkout, which may hold
   someone's unfinished work):
   ```
   git fetch -q origin main
   git merge FETCH_HEAD --no-edit
   ```
   - Only `CHANGELOG.md` conflicting (the usual case: every branch adds an entry at the top): run
     `python scripts/changelog_merge.py` (keeps both entries, a blank line between, line endings kept, prints entries
     that lack a `Summary:` line). Then `git add -A`, commit `Merge main into <branch>` and push.
   - Anything else conflicting (code, `clients.md`, `CLAUDE.md`): read both sides and keep the intent of both; ask Aaron only
     when it needs a product decision.
   - Run the tests for what you touched (section 3) before pushing. The push restarts CI: wait for it again.
3. **If CI fails**, read the log (`gh run view --job <id> --log-failed`). A failure in
   `tests/test_ars_launcher_web.py::test_changing_cycle_warms_the_new_one` is the known flaky one (it is fixed by resetting the
   selected cycle at the start of the test); rerun the failed job once with `gh run rerun <run> --failed` before digging.
   Anything else is a real failure: fix it on the branch, add the check that would have caught it.
4. **Merge** with `gh pr merge <N> --repo aburgard-csi/Velocity_Reporting --merge` (merge commit, as every PR here). When two PRs are open,
   merge one, then merge `main` into the other (it will conflict on CHANGELOG again), wait for its CI, then merge it.
5. **Check `main`**: the push to `main` starts its own run (the first can be cancelled by the next push; watch the NEWEST):
   `gh run list --branch main --limit 1`, then `gh run watch <id> --exit-status`. A red `main` blocks a release.

## 2. Release CSM Sheila

Only when asked. `main` must be green at the commit being released.

**Run the release script from the tasks checkout** (`RPE_TASKS_CHECKOUT` in `.env`, today `C:\Projects\RPE-Tasks`), not from
`C:\Projects\RetailPerformanceEngine`. The script releases `origin/main` either way, but the OUTER script that runs is the copy
in the folder you start it from, and only a current copy has the step that moves the tasks checkout afterwards
(2026-11-24: the working checkout sat on an old branch, so its copy lacked the step and the tasks checkout had to be moved by hand).

```
$env:RPE_DATA_ROOT = '\\PADMIS105\Velocity_company\CSM_Reporting'      # needs the VPN off-site
powershell -ExecutionPolicy Bypass -File C:\Projects\RPE-Tasks\scripts\release_launcher.ps1
```

The default releases `origin/main` from its own worktree, never a working tree. The output prints the stamp
(`released <date> <time> ... at <sha> (on origin/main, clean)`) and `tasks checkout ... now at <sha>`: quote both back.

**Check the tasks checkout moved.** The 08:00 source watch, its 08:10 watchdog and the 08:20 ILS analysis landing run from it,
so it must sit on the released commit:

```
git -C C:\Projects\RPE-Tasks log --oneline -1          # must match the <sha> in the stamp
```

If it did not move (the output said "left alone" or "not set", or the script ran from an old copy), move it by hand, only
when `git -C C:\Projects\RPE-Tasks status --porcelain` is empty: `git -C C:\Projects\RPE-Tasks fetch -q origin main` then
`git -C C:\Projects\RPE-Tasks checkout --detach <sha>`. Never edit files in that checkout; its `.venv` (junction) and `.env`
(hard link) are the real checkout's.

Then tag the backup and push the tag:

```
git tag -a backup-<YYYY-MM-DD>-release[-N] <sha> -m "Backup of origin/main as released <date>"
git push origin backup-<YYYY-MM-DD>-release[-N]
```

A release reaches each PC the next time its launcher starts (the .bat copies `Tools\RPE` to `%LOCALAPPDATA%\RPE\Code` when the
stamp changes), so tell Aaron to close and reopen Sheila. `clients.md` ships with the code: a roster change reaches the PCs only
through a release. Use `-Runtime` only when the libraries changed.

## 3. Test like CI

CI runs against an EMPTY `RPE_DATA_ROOT`. Run the suite the same way or tests that need the share fail for the wrong reason:

```
# an empty root with three subfolders
mkdir <scratch>\empty_root\Inputs, <scratch>\empty_root\Outputs, "<scratch>\empty_root\Build Artifacts"
$env:RPE_DATA_ROOT = '<scratch>\empty_root'
C:\Projects\RetailPerformanceEngine\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider     # the whole suite
... -k "sheila or launcher or changelog"                                                                 # what you touched
```

Use the repo `.venv` (the Store `python` has no pytest). A change to `templates/`, `build/` or `validation/` also needs
`validation/qa_all.py` (CLAUDE.md, QA gate).

## Gotchas (each of these cost time)

- **PowerShell strings:** a backtick-b inside a double-quoted string is a BACKSPACE character (it ate the quote in a CHANGELOG entry).
  Write multi-line text with a here-string `@'...'@` or the Write tool, not an inline double-quoted string. `\n` inside a Python
  heredoc passed through a shell becomes a real newline: write the Python to a file instead.
- **Line endings:** files here are often CRLF. Read with `newline=""`, detect `"\r\n" in text`, and write back with `newline=""`;
  never `.replace("\n", nl)` on text that already holds `\r\n` (it makes `\r\r\n`).
- **Commit messages and PR bodies:** end them with the attribution lines the session's own attribution reminder gives (the
  `Co-Authored-By:` model line changes with the model; never copy one from an old commit). Use `git commit -F <file>` and
  `gh pr create --body-file <file>`, with the file written by the Write tool: a message file written any other way has shipped as a
  stray test string ("x", 2026-11-24) and once with a BOM in the subject. Look at `git log -1` before pushing; a pushed message is
  never amended (no force-push), so a wrong one gets an empty follow-up commit carrying the right message.
  Push from PowerShell. Every CHANGELOG entry starts with a `Summary:` line.
- **Scheduled tasks run from the tasks checkout**, never from a working checkout: re-registering one (`register_watch_task.ps1`,
  `register_watchdog_task.ps1`, `register_ils_landing_task.ps1`) takes `-Repo C:\Projects\RPE-Tasks`, and only with Aaron's yes. A
  task registered with a fixed UTC offset drifts an hour at each clock change; after re-registering, check
  `Get-ScheduledTaskInfo` shows 08:00 / 08:10 / 08:20 local.
- **Auto-fix and old heads:** an Auto-fix conflict or failure event can arrive for a PR already merged, or for a head already
  replaced; check `gh pr view <N> --json state,headRefOid` before acting, and say so when there is nothing to do.
- **No client data in git, no hardcoded paths** (`rpe_env` resolves everything).
- **Releases include `clients.md`:** a roster edit that is merged but not released is invisible in Sheila.
- A merged PR's branch worktrees can be removed (`git worktree remove`) once nothing else needs them.
