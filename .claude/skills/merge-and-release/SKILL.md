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

```
$env:RPE_DATA_ROOT = '\\PADMIS105\Velocity_company\CSM_Reporting'      # needs the VPN off-site
powershell -ExecutionPolicy Bypass -File scripts\release_launcher.ps1
```

The default releases `origin/main` from its own worktree, never a working tree. The last line prints the stamp
(`released <date> <time> ... at <sha> (on origin/main, clean)`): quote it back. Then tag the backup and push the tag:

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
- **Commit messages and PR bodies:** commits end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; PR bodies end with
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Use `git commit -F <file>` and `gh pr create --body-file <file>`.
  Push from PowerShell. Every CHANGELOG entry starts with a `Summary:` line.
- **No client data in git, no hardcoded paths** (`rpe_env` resolves everything).
- **Releases include `clients.md`:** a roster edit that is merged but not released is invisible in Sheila.
- A merged PR's branch worktrees can be removed (`git worktree remove`) once nothing else needs them.
