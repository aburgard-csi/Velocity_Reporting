# Retail Performance Engine

Builds the monthly client review decks for Velocity Solutions' three retail
programs — **ARS** (Account Revenue Solution), **ICS** (Invitation Checking
System) and **MRPC** (MyRewards Premium Cards) — from each client's raw data.

One client gets one deck: a single-program client gets that program's deck, a
multi-program client gets the combined one.

## Build a month

```bash
python3 scripts/build_month.py 2026.08 <staging-dir>
```

Builds every active client in `clients.md`, validates each deck, and stages them
without touching the delivery folder. Exit code is the number of clients that
failed, so it can gate a delivery. Takes about seven minutes.

Then check the gate and the tests:

```bash
python3 validation/qa_all.py        # unit suite, then every deck rule
pytest tests/                       # 392 tests, ~14s
```

## Where things live

Data never lives in this repo. `RPE_DATA_ROOT` (see `.env.example`) points at the
pipeline tree under `RPE_DATA_ROOT`:

| | |
| --- | --- |
| `Inputs/ODDD/` | raw ODD extracts, one zip per client |
| `Inputs/DCOs/`, `ARS Workbooks/`, `MRPC Analyses/`, `ICS Workbooks/`, `ICS Charts/`, `CashPlease/` | one folder per kind of input, sorted on arrival (`rpe_env.INPUT_KIND_DIRS`) |
| `Inputs/VIP Data/` | ICS and MRPC client sheets pulled from VIP |
| `Inputs/Logos/` | client logos |
| `Outputs/` | finished decks, and nothing else |
| `Build Artifacts/` | build evidence — provenance sidecars |

In the repo: `build/` (the pipelines and their shared layer), `templates/` (the
per-program deck shells), `fonts/` (committed so both machines render
identically), `validation/`, `tests/`, `scripts/`.

## The companion files

Each of these owns one kind of decision. They are the reason the pipeline can be
rebuilt from scratch without guessing.

| File | Decides |
| --- | --- |
| **`CLAUDE.md`** | How the pipeline works and the rules it must follow — file locations, build machinery, the validation gate, and the standing rules (fix the builder not the deck; state missing data, never zero it). Start here. |
| **`clients.md`** | Which clients get which programs, and what each client is called. Presence of a data file is never a signal to build — this file is. |
| **`CHANGELOG.md`** | Every change that moves a number on a client-facing slide, or changes where a number comes from, with the reason. Newest first. |
| **`templates/STYLE.md`** | How a slide should look — colours, type roles, chart conventions, the two different "months" a deck reports. |
| **`templates/TEMPLATES.md`** | What each template shell contains and how to re-materialize one. |
| **`.claude/agents/*.md`** | The per-program build instructions an agent follows: `ars-deck`, `ics-deck`, `mrpc-deck`, `oddd-optimizer`. |
| **`docs/PRD-*.md`** | The portability and response-rate work, and what was decided during it. |

## Two rules worth knowing up front

**Fix the builder, never the deck.** A layout or number defect is corrected in
the builder, the geometry contract or the template shell, then rebuilt. Editing
a delivered deck fixes one client and leaves the rest broken.

**Decks are built from the template shells, never cloned from another client's
deck.** Cloning carries the previous client's numbers, captions and speaker
notes forward, and a figure that was never swapped looks exactly like one that
was.
