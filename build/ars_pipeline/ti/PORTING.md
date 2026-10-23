# Porting v5 analyses into `ti/`

The Transaction Intelligence cut carries analyses from James Gilmore's ARS v5 engine
(`JG-CSI-Velocity/v5-claude-automation-8.26`, ported at `a491b5c`). These rules keep a
ported figure checkable against v5's and keep the cut out of the ARS deck's way.

## Layout mirrors v5

| v5 (`02-Scripts/`) | here (`build/ars_pipeline/ti/`) |
| --- | --- |
| `core/` and `ars/core/` | `core/` |
| `ars/monthly_analysis/` | `monthly_analysis/` |
| `ars/transaction_intelligence/` | `transaction_intelligence/` |
| `ars/deck/` | `deck/` |

Mirroring keeps v5's relative imports valid. Absolute imports are rewritten
(`core.` and `ars.core.` → `ti.core.`; `ars.<package>` → `ti.<package>`), and nothing else.

## Rules

1. **Logic is copied unchanged.** Each ported file starts with a line naming its v5 path and
   commit. A change to what a function computes is its own pull request with its own
   CHANGELOG entry, never part of a port.
2. **Inputs come through RPE.** The ODD through `ti/odd.py` (`Inputs/ODDD/<id>_ODDD.zip`
   via `rpe_env`), transaction files through `rpe_env.txn_files()` / `open_txn()`, every
   other input through `rpe_env.input_dir(<kind>)`. No path is written into a ported file.
3. **Client config comes through `ti/config.py`.** A v5-shaped config file when one is
   supplied (exact parity with v5), else derived from the ARS database code tables, and
   stated. v5 and the code tables disagree on eligibility for most clients (1615 Cape &
   Coast: 22,103 eligible on v5's curated codes, 20,652 on the tables' active / actively
   offered flags); which one the cut ships with is an open decision.
4. **Slides draw through the RPE frame.** Ported slide builders keep their v5 call shape;
   the helpers they call are RPE's (`brand`, `shapes`, `cover_divider`, `fit_layout`), and
   every slide's notes carry a Source line (`ti/frame.notes`).
5. **Nothing of the ARS deck is touched.** Where a ported slide overlaps one in the ARS deck
   or the opt-in James views, both are kept and the overlap is recorded in
   `docs/migration/DUPLICATES.md`.
6. **Tests come with the port.** v5's own tests for a module are ported beside it as
   `tests/test_ti_<module>.py`, with the same import rewrite, plus whatever RPE-side test
   the wiring needs.
7. **Pandas 2 string semantics.** v5 runs pandas 2.3, this repo pandas 3. Everything the cut runs
   is inside `ti.compat.legacy_strings()` (the entry points wrap it; `test_ti_*` tests get it from
   `tests/conftest.py`), so ported code sees `astype(str)` turn a missing value into "nan" as it did
   in v5. Never set the option process-wide: Aaron's code runs on pandas 3's defaults.
