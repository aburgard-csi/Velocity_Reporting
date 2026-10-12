# Working in this repo with Claude Code (for collaborators)

Hand this file to your Claude Code session at the start (or just say "read docs/COLLABORATORS.md").
`CLAUDE.md` is loaded automatically and holds the pipeline rules; this file adds what a
**collaborator's** session needs to know so it does not step on Aaron's machine, the shared
`CSM_Reporting` tree, or the clients' decks.

## The short version

1. Work on a branch and open a pull request. Never push to `main`.
2. Run the unit suite before you push: `.venv\Scripts\python -m pytest tests -q`.
3. Never put client data in git, and never hardcode a path.
4. Do not run the release, the scheduled-task registration or the source watch. Those are Aaron's.
5. Unsure whether a change moves a client-facing number? Stop and ask.

## Set-up (once per machine)

- Clone the repo, create the virtual environment in the repo root (`.venv`) and install
  `requirements.txt`. Use `.venv\Scripts\python` for everything; the Windows Store `python` has no pytest.
- Copy `.env.example` to `.env`. `RPE_DATA_ROOT` is `\PADMIS105\Velocity_company\CSM_Reporting`;
  off-site that needs the VPN. All paths come from `RPE_DATA_ROOT` through `build/rpe_env.py`.
  If a path is wrong, fix `.env`, never the code.
- The shell is Windows (PowerShell or Git Bash). The pipeline uses PowerShell scripts, scheduled
  tasks and Outlook COM, so it is not portable to Mac or Linux.

## Branches and pull requests

- `main` is protected by design: pull requests only, one approving review, and the `tests` check
  (the unit suite on a Windows runner against an empty data root) must pass.
- `.github/CODEOWNERS` asks Aaron to review `build/`, `validation/`, `templates/`, `clients.md`,
  `CLAUDE.md`, `.github/` and the release and task-registration scripts. A wrong change there ships a
  wrong deck without any test noticing, so make those PRs small and say what output they change.
- Branch names: `fix/...`, `feat/...`, `docs/...`, `perf/...`. One purpose per PR.
- If `git push` hangs from Git Bash, push from PowerShell.
- Commit messages end with the attribution line your Claude client gives you. Do not add other
  attribution.
- Do not merge your own PR unless Aaron has said to. Do not force-push. Do not delete branches that
  are not yours (for example `test/unified-analysis` is James's).
- The tests can fail on a PR that did not touch the failing code. Say so in the PR and tell Aaron;
  do not skip or delete a test to get green.

## What not to run

| Do not run | Why |
| --- | --- |
| `scripts/release_launcher.ps1` | It copies code to the share every CSM's launcher runs. Aaron releases. |
| `register_watch_task.ps1`, `register_watchdog_task.ps1` | They change scheduled tasks on a machine. |
| `scripts/watch_sources.py --copy / --mail / --prune` | The 08:00 copy runs once a day; a second copier duplicated a file. `--dry-run` is fine. |
| Anything that writes to `Outputs/` or `Inputs/` by hand | Builds write there. Do not delete or overwrite files on the share. |
| `scripts/dashboard.py`, `ars_launcher_web.py` on a shared port | They bind 127.0.0.1 only; run one copy per machine. |

Read-only inspection of the share is fine. A build for a client goes through CSM Sheila or
`scripts/ars_launcher.py build <id>`, not through hand edits to a deck.

## Rules that have each caused a real error

- **Never edit a finished deck, and never start a build from another client's deck.** Fix the builder
  or the template shell in `templates/`, then rebuild. A cloned deck carries the last client's
  numbers into the next.
- **No client-identifiable data in the repo.** That means logos, ODD rows, member names, account
  numbers, branch names and result files. Tests use the synthetic fixture in `tests/fixtures/`.
- **Do not hardcode a path, a client's name or id, or a CSM's contact card.** Roster and programs
  come from `clients.md`; paths from `rpe_env`; contacts from `CSM Contacts.csv`.
- **Do not map a code on your own.** Reg E, account status and product codes that do not map are a
  correction on the client's code sheet. Ask; do not guess.
- **Comparisons use complete months only** (`build/month_complete.py`). Do not add a "latest month"
  read of an activity series any other way.
- **A claim needs a figure.** A sentence that says a measure moved must be derived from the data, not
  written as a constant (see "Describing movement" in `CLAUDE.md`).
- **Missing data is stated, never zeroed.** Do not drop a slide or render a 0% for absent data.
- **Every slide lists its data source in the speaker notes**, naming the client being built.
- **Resolve slides by title, never by index.**
- **Writing style:** the banned-word list in `CLAUDE.md` applies to all client-facing text.
- **Executive Summit one-pagers are hand-built per attendee.** Do not automate or schedule them, and
  do not choose the metrics.
- **Claude cannot reach the ILS, VIP or MRDB databases.** SQL in `sql/` or `scripts/sql/` is run by a
  person who pastes back the result. Never put results or customer lists in the repo.

## Before you open a PR

1. `.venv\Scripts\python -m pytest tests -q` passes.
2. If you changed `templates/`, `build/` or `validation/`, run
   `.venv\Scripts\python validation\qa_all.py` too. A layout DRIFT warning means you touched slides you
   did not mean to; review it, and `--snapshot` only if the change is intentional.
3. A bug that got past the gate gets a new check that would have caught it, not only a fix.
4. Add a `CHANGELOG.md` entry at the top of **Changes, newest first** if you changed behaviour or
   what a slide renders, even when no number moves. Start it with a `Summary:` line of one or two
   plain sentences for a CSM. (There is no "unreleased" section: a release copies this file with
   the code, and Sheila's change log page names the release it is in.)
5. If you added, moved or removed a file, update the file map at the end of `CLAUDE.md`.
6. In the PR description, say what you ran, what you did **not** run (anything needing the VPN or
   Outlook), and which client-facing output could change.

## Editing tips for Claude

- Many files use CRLF line endings. Edit with the Edit tool, or match the file's endings if you
  script a replacement; a string match written with `\n` will miss.
- `build_ars_gen.py`, `validate_deck.py` and `ars_launcher_web.py` are thousands of lines. Read the
  part you need, not the file.
- Shared code in `build/` (`brand.py`, `shapes.py`, `periods.py`, `month_complete.py`) serves all
  programs. A change there can alter ARS, ICS, MRPC and CashPlease decks at once.

## Who to ask

Aaron Burgard owns the pipeline, the roster and releases. If the right answer is not in `CLAUDE.md`
or here, ask rather than infer: this repo has shipped plausible-looking wrong figures before.
