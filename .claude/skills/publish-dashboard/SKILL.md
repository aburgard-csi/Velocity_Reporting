---
name: publish-dashboard
description: Refresh the RPE Client Performance artifact by hand and republish it to its existing URL when the figures changed. Use after any deck delivery or rebuild (standing rule), when Aaron asks to refresh or republish the performance dashboard, or to re-arm comment replies on it. Rebuilds from the released code, diffs the page against the live artifact, publishes in place, and marks it published. Never creates a new artifact.
---

# Refresh and republish the performance dashboard

"RPE Client Performance" is a static page with its dataset embedded, rebuilt by `scripts/refresh_performance_dashboard.py`
from the same inputs the decks read. The script never publishes; Claude does, to ONE URL that people hold:

- `https://claude.ai/artifact/F4jLMLqxmQdBNYXpJHH6We` (the `claude.ai/code/artifact/71e542f6-...` form opens the same page).

The 08:30 Claude scheduled task `rpe-dashboard-refresh` does all of this every morning; this skill is for hand runs.
Standing rule (Aaron, 2026-09-15): after any deck delivery, refresh, and republish if it changed.

## 1. Sends recorded on the page (if any)

The page's roster has a "Mark sent" button that writes to the artifact's own database, collection `deliveries`. Read it
with the `ArtifactData` tool: action `list`, `url` the URL above, `collection` `deliveries`, `out_dir` a new scratch folder
(each row lands as `<out_dir>/deliveries/<doc_id>.json`; page with `query.cursor` if the result gives a `next_cursor`).
Usually empty. When it holds rows, pass the folder to step 2 as `--merge-sent <out_dir>` (the script reads every `.json`
under it) and it folds them into `deliveries.json`. Never hand-edit that file, and never write to the artifact's database.

## 2. Refresh, from the released code

Run it from the **tasks checkout** (`C:\Projects\RPE-Tasks`), not the working checkout, and name the real checkout for the
page's Live Review commands:

```
$env:RPE_REPO = 'C:\Projects\RetailPerformanceEngine'
C:\Projects\RPE-Tasks\.venv\Scripts\python.exe C:\Projects\RPE-Tasks\scripts\refresh_performance_dashboard.py [--merge-sent <folder>]
```

- It prints a per-client summary, `html <path>` (the page, `Build Artifacts/perf_dashboard/rpe_dashboard.html`) and ends
  `STATUS: changed` or `STATUS: unchanged`. Changed means the figures moved (the hash leaves out the generation date).
- The page lists ONE CSM's clients: `--csm "<Name>"`, else `RPE_DASH_CSM`, else Aaron. There is no all-CSMs option.
- `--period <yyyy.mm>` rebuilds an older month; `--force` reports changed whatever the hash says.
- **Off the VPN the refresh fails.** Say so plainly. Nothing new can be published; republishing the unchanged local copy
  only re-arms comment replies.
- **If the summary lists every CashPlease client as MISSING**, do not publish even on `changed`: it would drop the whole
  CashPlease section from the live page. Report it.

On `unchanged`, say so in one line and stop, unless Aaron asked to re-arm comment replies.

## 3. Publish, only when changed (or to re-arm replies)

1. **Copy the page into the session scratchpad.** The Artifact tool cannot publish from the share.
   ```
   Copy-Item '<RPE_DATA_ROOT>\Build Artifacts\perf_dashboard\rpe_dashboard.html' '<scratchpad>\rpe_dashboard.html'
   ```
2. **Read the live artifact first** (Artifact `read`, the URL above). It saves the live page to a local file.
3. **Diff with the dataset line removed.** The data is one `const DATA = ...;` line; everything else is the template:
   ```
   $a = Get-Content '<live page file>'       | Where-Object { $_ -notmatch '^\s*const DATA\s*=' }
   $b = Get-Content '<scratchpad>\rpe_dashboard.html' | Where-Object { $_ -notmatch '^\s*const DATA\s*=' }
   Compare-Object $a $b
   ```
   The non-data diff must be only template changes you know were merged and released (`scripts/perf_dashboard_template.html`,
   `scripts/perf_workflow.html`). Anything else (an old table style, a section gone) means the page was built from stale
   code: **STOP** and find out why before publishing.
4. **Publish to that URL** (Artifact `publish`, `url` = the URL above, `file_path` = the scratchpad copy, a label like
   `Refresh <date>`). Never without `url`: that would create a new artifact and strand the link people hold. Do not pass
   `capabilities` (omitting it keeps the page's `db` capability, which the Mark sent button needs; `{}` would revoke it),
   and do not pass `icon` on a republish.
5. **Mark it published:**
   ```
   C:\Projects\RPE-Tasks\.venv\Scripts\python.exe C:\Projects\RPE-Tasks\scripts\refresh_performance_dashboard.py --mark-published
   ```

## 4. Report

The period the page shows, how many clients, sends merged from the page, whether it was republished (and the non-data diff
in a line), and any client the summary listed as MISSING a section.

## Gotchas

- **Stale template, wrong page (2026-11-24).** A refresh from the working checkout drew the OLD table style, because that
  checkout's `scripts/perf_dashboard_template.html` was behind `main`. The tasks checkout holds the released code; use it,
  and let the non-data diff catch anything else.
- **`RPE_REPO`** is read only by this script, for the Live Review commands the page copies to the clipboard. Without it the
  commands name the tasks checkout.
- **Never edit the published copy or the page in the scratchpad.** Change `scripts/perf_dashboard_template.html`, merge,
  release, refresh.
- **Do not copy the page to `CSM_Reporting\Notes`** or share it elsewhere; Aaron decides who sees it.
- **No client data in git**: the dataset and pages live in `Build Artifacts/perf_dashboard/` and the scratchpad only.
