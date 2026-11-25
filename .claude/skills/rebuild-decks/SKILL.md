---
name: rebuild-decks
description: Rebuild a set of clients' Executive Review decks for one period with the launcher, one build at a time, from the released code. Use when Aaron asks to rebuild decks after a fix, rebuild a CSM's book or a list of clients, or rebuild the TI or Companion decks. Asks the scope first, runs the loop in the background with a progress file, checks the peer slides, and reports rebuilt, failed and skipped per client.
---

# Rebuild decks

A rebuild REPLACES a deck in `Outputs/<CSM>/`, and each CSM reviews, PDFs and emails their own decks from there. So the
scope is a decision, not a default. The launcher (`scripts/ars_launcher.py`, the same code Sheila's Build button runs) does
the build, the validation gate and the filing; this skill only drives it over a list. Never hand-edit a deck.

## 1. STOP: agree the scope with Aaron

Ask, and wait for the answer:

- **Whose decks.** Aaron's own clients, or other CSMs' too? Another CSM may already have reviewed or sent the deck you
  would replace: name those clients and their CSM and get Aaron's yes for them separately.
- **Which period** (`yyyy.mm`), and which clients (a list, or "every client with a deck in Outputs for that period").
- **Which decks.** The Executive Review only, or also the Transaction Intelligence decks (`--ti`) and the ARS Companion
  (`--companion`)? Each is a separate build of its own.

## 2. Plan each client

For each client, from the released code (step 3 says which checkout):

```
python scripts/ars_launcher.py status <id> --period <yyyy.mm>
```

- **Skip** a client whose status shows a STOP (missing or stale ODD, no workbook, expired Lift Matrix, not on the roster).
  Write down the STOP line: it is the reason in the report. Do not work around a STOP.
- **`--combined`:** Aaron's multi-program ARS clients ALWAYS get `--combined`; `rule_checks` in `scripts/ars_launcher.py`
  STOPs an ARS-only build for them. Other CSMs' clients get whatever they last built (the deck name in Outputs says
  `ARS` or `ARS-ICS-...`); ask when unsure. `build_programs` decides what a build carries (CashPlease rides on every
  build of a client who ships it as a section; a non-ARS client always builds everything with data).
- **Order:** ARS clients first, every other client after (see step 5, peers).

## 3. Run the builds: one at a time, in the background

Run them from the **tasks checkout** (`C:\Projects\RPE-Tasks`, the released code; its `.env` is a hard link to the real
one, so `RPE_DATA_ROOT` resolves the same). Never from a feature branch's worktree. One build at a time: builds share the
share's bandwidth, and Sheila on this PC must not be building at the same moment (her one-at-a-time lock does not cover a
command-line build).

The command for one client is:

```
python scripts/ars_launcher.py build <id> --period <yyyy.mm> --rebuild [--combined]
```

Write the loop to a `.ps1` file in the scratchpad with the Write tool and start it with the PowerShell tool's
`run_in_background`. It appends one line per client to a progress file:

```
$py = 'C:\Projects\RPE-Tasks\.venv\Scripts\python.exe'
$launcher = 'C:\Projects\RPE-Tasks\scripts\ars_launcher.py'
$period = '<yyyy.mm>'
$dir = '<scratchpad>\rebuild-<yyyy.mm>'
New-Item -ItemType Directory -Force $dir | Out-Null
$todo = @( @{id='<id>'; combined=$true}, @{id='<id>'; combined=$false} )
foreach ($c in $todo) {
    $a = @($launcher, 'build', $c.id, '--period', $period, '--rebuild')
    if ($c.combined) { $a += '--combined' }
    & $py @a *> (Join-Path $dir "$($c.id).log")
    "$(Get-Date -Format 'HH:mm') $($c.id) exit=$LASTEXITCODE" | Add-Content (Join-Path $dir 'progress.txt')
}
'DONE' | Add-Content (Join-Path $dir 'progress.txt')
```

(`$a`, not `$args`: `$args` is a PowerShell automatic variable.) Exit codes: 0 = in Outputs, 1 = not built or not put in
Outputs, 2 = bad arguments, 3 = a deck is already there and `--rebuild` was missing (`ASKED_EXIT`). The launcher's own
record of each build is `Build Artifacts/launcher/<period>/<id>/_launcher_result.json` (`result`, `delivered`).

**Watch the progress file, not the builds.** A Monitor KILLS its command after 30 minutes, so the builds never run inside a
Monitor; only a watcher does, re-armed as often as needed. Monitor commands run under bash:

```
f=/c/Users/.../scratchpad/rebuild-<yyyy.mm>/progress.txt; n=0
until grep -q '^DONE' "$f" 2>/dev/null; do c=$(wc -l < "$f" 2>/dev/null || echo 0); [ "$c" != "$n" ] && tail -n 1 "$f" && n=$c; sleep 60; done
```

A build takes 3 to 20 minutes; a dozen clients is a few hours.

**A deck that fails validation is NOT put in Outputs**, and the old deck stays where it was. That is the gate working.
Record it, carry on with the next client, and triage it afterwards with the `fix-deck-failure` skill. The FAIL lines
are in `Build Artifacts/launcher/<period>/<id>/<deck>.pptx.validation.txt`, the steps in `build.log` beside it.

TI and Companion builds are the same loop with `--ti` or `--companion` in place of `--combined` (they keep `--rebuild`).

## 4. Check the peer slides

Every Executive Review carries "How You Compare" slides (`build/peer_slide.py`). A measure is drawn only when at least
`MIN_PEERS` (5, `build/peer_compare.py`) OTHER clients have current data for it; otherwise the slide says it is left
out. After a deck lands, the launcher starts a background peer-reference update (`update_peer_reference`; its log is
`Build Artifacts/peer_reference_updates.log`).

Read each rebuilt ARS deck's peer slides:

```
python -c "import sys; from pptx import Presentation; p=Presentation(sys.argv[1]); [print(i, ' | '.join(s.text_frame.text.replace(chr(10),' ') for s in sl.shapes if s.has_text_frame)) for i, sl in enumerate(p.slides, 1) if any(s.has_text_frame and s.text_frame.text.startswith('How You Compare') for s in sl.shapes)]" "<deck>.pptx"
```

A slide saying a measure has fewer than 5 peers, on a measure the other rebuilt decks show, means the deck was built
before enough peers carried it: rebuild that client once more at the end.

## 5. Afterwards

1. **Refresh the performance dashboard** (the `publish-dashboard` skill). Standing rule: refresh after any delivery, and
   republish only when it changed.
2. **Report per client**, one line each: rebuilt (deck name), failed (the FAIL line, and that the old deck stayed), or
   skipped (the STOP line). Name any other CSM whose deck was replaced, so Aaron can tell them.

## Gotchas

- **Peer measures need peers first (2026-11-24).** The first five ARS decks rebuilt that day missed the account-growth
  measure ("How You Compare — Accounts Gained & Kept") because too few peers carried it yet, and had to be built a
  second time. Build ARS clients first, check the peer slides, and rebuild any that were built before the threshold.
- **Never build inside a Monitor** (killed at 30 minutes, mid-build). Background shell job plus a progress file.
- **Released code only.** A rebuild from a working checkout ships whatever is half-done in it.
- **`RPE_REPO` does not affect a build.** Only `scripts/refresh_performance_dashboard.py` reads it (for the Live Review
  commands on the dashboard page); set it for that step, not here.
- **`--rebuild` is required** for any client that already has a deck for the period, or the launcher exits 3.
- **Other CSMs review their decks.** Replacing one silently undoes their review.
- **No client data in git**: progress files and logs stay in the scratchpad or `Build Artifacts/`.
