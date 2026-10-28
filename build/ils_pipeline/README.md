# ILS analyses from v5 (proposal)

**Status: proposed, not agreed.** `CLAUDE.md` routes ILS to the hand-run `ils-prep-deck` skill
("not an RPE build"), and `docs/COLLABORATORS.md` limits James's v5 ports to
`build/ars_pipeline/ti/`. This folder exists only if Aaron agrees to it. Nothing here is wired into
a build, the launcher, Sheila, `clients.md` or any existing pipeline.

## What it holds

Two standalone ILS engines from James Gilmore's ARS v5 repo (`JG-CSI-Velocity/v5-claude-automation-8.26`,
ported at `7ba1e63`), each with its own extract and its own deck, each on its own branches:

| Engine | v5 | here | Input |
| --- | --- | --- | --- |
| Pre-go-live (PGL): reconcile a client's extract against the vendor's system dumps before go-live, board deck | `02-Scripts/ils/pre_go_live/` | `pre_go_live/` | `Inputs/ILS PGL/<id>/` |
| Kickoff: how the book is made up, where the NSF activity sits, how it is configured | `02-Scripts/ils/kickoff_analysis/` | `kickoff/` (later, its own branches) | to be agreed |

Neither engine reads the ODD or pairs with ARS. Neither overlaps `ils-prep-deck`, which reviews a
client already live on ILS.

## Rules (the same contract as `ars_pipeline/ti/PORTING.md`)

1. Logic is copied unchanged. Each ported file starts with a line naming its v5 path and commit.
2. Inputs come through `rpe_env.input_dir(<kind>)`; no path is written into a ported file.
3. Account codes are per-run inputs, as in v5: the first run returns a field summary and computes
   nothing, a person confirms the codes, and the codes used are recorded in the output. There is no
   client config for ILS.
4. v5's tests come with the port as `tests/test_ils_<engine>_<module>.py`.
