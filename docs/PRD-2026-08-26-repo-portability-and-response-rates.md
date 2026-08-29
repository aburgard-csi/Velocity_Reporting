# PRD — repo migration, cross-machine builds, response-rate fix, deck skills

Date: 2026-08-26
Owner: Aaron Burgard
Status: Phases 1-3 shipped; Phase 4 shipped as subagents rather than skills.
Last reviewed 2026-08-29.

---

## Problem

Four problems. They have to be solved in this order, because each one makes the
next safer.

**No version history.** The pipeline exists in at least three places — `build/`
in Google Drive, the Mac, and stale snapshots (`ARS Build Package.zip` from
July, `Marine deck build scripts.zip`, compiled `.pyc` files). Nothing indicates
which is current. A deliberate behavior reversal on 2026-08-20 is recorded only
as a comment inside an 80KB source file.

**Mac-only.** The code assumes macOS. `build_ars_gen.py` sets matplotlib's font
family to Carlito, which ships with LibreOffice and is absent from a stock
Windows box. matplotlib substitutes silently rather than failing, so charts
would render in a different face on the CSI machine with no warning. The helper
scripts have not been audited for absolute paths.

**Wrong denominators.** `NU 5+` and `Threshold Met` on the ARS Mailing Response
Summary divide by total accounts mailed rather than by each offer group's own
mailed count. Present in all nine 2026.08 ARS decks. See CHANGELOG.

**No repeatable build process.** Deck builds are ad-hoc, across seven product
combinations.

## Success criteria

1. The same client and period, built on the Mac and on the CSI machine, produce
   decks with identical slide text and identical numbers — proven by a
   validation script, not by eyeballing slides.
2. One repo is the only live copy of the pipeline. No client data in it.
3. Response rates report NU against NU recipients, TH against TH-10 through
   TH-25 recipients, and overall against total offers sent.
4. Seven deck entry points over four bodies of logic. Every rule written once.

## Scope

**In:** the `build/` tree; `CLAUDE.md`, `templates/STYLE.md`,
`templates/TEMPLATES.md`; repo scaffolding; path and font portability;
`metrics_gen.mail_summary`; the slide-12 block and its stale comment in
`build_ars_gen.py`; seven deck entry points over four logic bodies.

(This originally listed a `RUNBOOK.md`. It was never written, and the per-program
build steps live in `.claude/agents/{ars,ics,mrpc}-deck.md` instead — those are
what actually execute, so a separate runbook would be a second source to drift.
Reference updated 2026-08-29 rather than leaving a pointer to a file that does
not exist.)

**Out:** re-issuing the eight remaining 2026.08 decks — that follows the code
fix rather than preceding it. The slide 12 vs slide 13 responder-count mismatch,
which is a separate undiagnosed bug. ICS and MRPC calculation changes beyond
making them run on Windows.

## Constraints

- The repo is private. Claude in the chat interface cannot read it — private
  repos need a token, and credentials don't go in chat. Repo-level work happens
  through Claude Code on a machine with the repo checked out. Chat handles
  review, Drive text reads, and drafting.
- Google Drive binary downloads are unreliable through the connector; a 4.7MB
  deck was refused outright. Text files (`.py`, `.md`) read fine.
- Data stays in Drive and is reached through Drive for Desktop. The mount root
  differs per machine and must not be hardcoded anywhere.
- matplotlib silently substitutes a missing font rather than failing.

## Plan

### Phase 1 — repo

Create the repo (done: `aburgard/RetailPerformanceEngine`, private). Push
`build/` from the Mac, which is authoritative. Exclude `.pyc` files, the July
zips, and the two `data/` folders. Add `.gitignore`, `CHANGELOG.md`, this PRD,
and `requirements.txt` before the first commit.

Diff the Mac tree against the Drive copy to find drift before deleting anything
from Drive. Deleting the zips and compiled files is one-way and gets its own
confirmation.

### Phase 2 — portability

Grep every module for absolute paths: `charts_gen.py`, `restyle_fonts.py`,
`render_lift.py`, `fit_layout.py`, `slide_geometry.py`, `product_mix_slide.py`,
`base_tab_extract.py`, and the ICS and MRPC builders.

Introduce `RPE_DATA_ROOT`, resolved per machine, pointing at
`…/My Drive/Work/RPE Pipeline`. This joins the existing `RPE_BUILDDIR` and
`RPE_REF` convention.

Replace the bare font assignment with explicit resolution that raises on a miss.
Install Carlito on Windows so both machines render the same face, rather than
switching to Calibri on one side.

Build one client on both machines and diff the output.

### Phase 3 — calculation

Apply the `mail_summary` change described in CHANGELOG. Update the six-value row
unpack in `build_ars_gen.py`. Add a warning when the NU and TH splits fail to
reconstitute the mailed population, so an unexpected `Mail` value can't silently
drop accounts from both denominators. Rewrite the stale comment block.

Rebuild CoastLife 1705 from the ODD and compare against the v3 stopgap figures.
Then the remaining eight decks.

### Phase 4 — skills

Three product skills (ARS, ICS, MRPC), each owning its pipeline end to end. One
composition skill owning what is genuinely different about a merged deck:
section ordering, deduplicated front matter, a single contact slide,
renumbering, and one source-note pass.

Seven entry points — ARS, ICS, MRPC, ARS+ICS, ARS+MRPC, ICS+MRPC, all three —
each thin, naming a product set and handing off. Built last, on code that is
correct and versioned.

## Decisions

**Filenames use the product hierarchy, not a product list.** ARS > ICS > MRPC.
The parsed token is the highest-ranked product present, because VIP expects a
single value there. Display text after the client name may name both products.

```
1705-2026.08-ARS-CoastLife Credit Union ARS & ICS Results v1.pptx
 │    │       │   └ display text (not parsed)
 │    │       └ product token — highest-ranked product in the deck
 │    └ period
 └ client_id
```

No collision risk: a client receives either a single-product deck or a combined
deck in a given period, never both.

**Data in Drive, code in git.** Workbooks, ODD extracts, DCO files and finished
decks stay in Drive. Nothing client-identifiable enters the repo.

## Resolved during drafting

- TH covers all four threshold strategies — TH-10, TH-15, TH-20, TH-25. Five
  offer levels total including NU.
- CoastLife v3 is a stopgap, not a reference implementation.
- The ODD is the source for response rates. The workbook is out.
- The ODD does carry per-account mailed strategy, so the denominators exist.

## Open

- The literal Drive for Desktop path on the CSI machine, for `RPE_DATA_ROOT`.

## Closed 2026-08-29

- **`ics_pipeline/data/` and `mrpc_pipeline/data/` hold CLIENT DATA**, not
  runtime fixtures — `1549-Wellworth Bank`, `1705_ics.json` and the like,
  correctly gitignored and untracked. They therefore have to resolve through
  `RPE_DATA_ROOT` like every other input, or success criterion 1 is unreachable
  for ICS and MRPC on a fresh checkout.
- **The skills shipped as subagents**, not as named commands:
  `.claude/agents/{ars,ics,mrpc}-deck.md` plus `oddd-optimizer`, invoked in plain
  language and composed by `build/assemble_combined.py`.
