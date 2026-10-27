<!-- Read docs/COLLABORATORS.md before filling this in. One purpose per PR. -->

## What changes

<!-- A sentence or two for a CSM, the same as the CHANGELOG entry's Summary line. -->

## Client-facing output that could change

<!-- Which slide, figure, file name or folder — or "none". A change under build/, validation/ or templates/ needs Aaron's review. -->

## What I ran and did not run

- [ ] `.venv\Scripts\python -m pytest tests -q` passes
- [ ] `validation\qa_all.py` run if `templates/`, `build/` or `validation/` changed (DRIFT reviewed)
- [ ] `CHANGELOG.md` entry added, starting with `Summary:`
- [ ] `CLAUDE.md` file map updated for any file added, moved or removed
- Not run (VPN, Outlook, the share): 

## Transaction Intelligence branches only (`feat/ars-ti/...`)

<!-- Delete this section for any other PR. See "Transaction Intelligence branches" in docs/COLLABORATORS.md. -->

- Stage and base branch: 
- Ported from v5 (path and commit): 
- Parity against v5 (`scripts/ti_parity.py`): 
- New rows in `docs/migration/DUPLICATES.md`: 
- [ ] Nothing outside `build/ars_pipeline/ti/`, `ti_build.py`, `build_ti_gen.py`, `scripts/ti_parity.py`, `tests/test_ti_*.py`, `DUPLICATES.md`, the `ti/` file-map lines and `CHANGELOG.md` is changed
- [ ] No name Sheila's button depends on changed (the table in COLLABORATORS.md) — or the launcher and `tests/test_ti_launcher.py` are updated here and it is said above
- [ ] Every ported slide's notes carry a Source line; no client-identifiable data in the repo
