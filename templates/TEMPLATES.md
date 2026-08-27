# Deck Templates — derived from the combined reference deck

All three program templates come from one reference: the latest combined Executive Review,
which carries ARS + ICS + MRPC sections plus the shared shell and the ARS appendix. Each
program subagent clones this deck and keeps only its own section (plus the shared shell),
then swaps the client's numbers and charts. (Filenames in this repo are generic — no client
names; per-client specifics live in the build instructions, `.claude/agents/ars-deck.md`.)

## Reference deck

- **File:** `templates/multi-product_reference_deck.pptx` (the combined reference; client-neutral filename).
- **Period:** latest available (currently data thru June 2026).
- Update whenever a newer combined deck becomes the reference — replace
  `templates/multi-product_reference_deck.pptx` with the newer deck (keep the generic filename).

## Section map (slide numbers in the reference deck; total 67)

| Slides | Section | Belongs to |
| --- | --- | --- |
| 1–3 | Shared shell — Title, About the Summit, Agenda | all (adapt per program) |
| 4 | ARS section divider | ARS |
| 5–29 | ARS content — Program Overview, Financial Performance, **Lift Matrix (MM) / Monthly Summary (SM)**, Debit Usage Segmentation, Average Ticket, Mailing Insights (11–18), Debit Card Review (19–24), Reg E Review (25–28), ARS Key Takeaways (29) | ARS |
| 30–44 | ICS content — divider (30), Power of Referrals, Referral Trend, Results by Branch, Performance of ICS Accounts, ICS Revenue, ICS Financial Summary, vs Velocity Benchmark, Mystery Shop, education/reference slides (39–44) | ICS |
| 45–51 | MRPC content — divider (45), Enrollments by Month, Enrollments by Channel, Enrollment vs Goal, Retention, Revenue, Key Metrics | MRPC |
| 52 | Questions & Discussion | all |
| 53–67 | ARS Appendix — Additional ARS Respondent Insights | ARS (appendix module) |

## How each program uses this

- **ars-deck** keeps slides 1–29, 52, 53–67. Swaps the MM/SM performance slide per path.
- **ics-deck** keeps the shell (1–3, adapted), 30–44, and a closing/discussion slide.
- **mrpc-deck** keeps the shell (1–3, adapted), 45–51, and a closing/discussion slide.

Each single-program deck re-numbers its own agenda and slides after trimming.

## Swap targets (what changes per client)

Client name and id, period label, all headline figures and table values, chart data,
branch names/counts, and every source line (ODD filename + pull date for ARS; workbook /
VIP dashboard references for ICS and MRPC). Everything else — layout, colors, section
dividers, education/reference slides — stays as-is.

## Materializing the stripped templates

The reference deck is large (~6.5 MB). Once it's in the source-data location, the first run
of each subagent should trim the reference to its section and save the stripped template in
this `templates/` folder as `ars_template.pptx`, `ics_template.pptx`, `mrpc_template.pptx`.
After that, each program clones from its local stripped template and no longer needs the
full reference binary. Re-materialize whenever the reference deck updates.

**Bundled templates already in this copy.** All three programs ship with a stripped template
under the repo: `templates/ars_template.pptx` (46-slide ARS shell — cleaned + genericized
2026-07-24; client-neutral "Union Financial" dummy client, standardized logos/slide numbers),
`templates/ics_template.pptx`, `templates/mrpc_template.pptx`. Builds run
from these directly; the full `multi-product_reference_deck.pptx` is only needed to re-materialize a
template when the reference updates.

## Version log (latest = files in this folder; updated in place)

| Date | Files | Change |
| --- | --- | --- |
| 2026-07-24 v3 | `ars_template.pptx`, `ics_template.pptx`, `mrpc_template.pptx`, `multi-product_reference_deck.pptx` | Transaction Increase chart vertically centered; MRPC Card Portfolio donut+labels enlarged; MRPC Contact placeholder prompt boxes stripped (and globally via `fit_layout`); ICS E-Learning Library Guide text enlarged (24/18pt); all changes mirrored to the multi-product reference. All four validate 0 FAIL. |
| 2026-07-24 v2 | same files | Per-slide geometry contract (Reg E stack, take-rate centered, Product Mix source bottom-center, equal Swipes/NSF), caption breathing-room + collision validation, styling pass on ICS/MRPC templates, Union Financial neutralization. |
| ≤2026-07-17 v1 | originals | Marine-derived; pre-QA (backups in `archive/pre_qa_backup/`). |

**Convention:** templates are updated **in place** — the files in `templates/` are always the
latest. Superseded copies go to `archive/pre_qa_backup/` if a rollback point is needed.

**2026-07-24 v4 (LATEST):** `ics_template.pptx` is now a **full 28-slide Union Financial demo
deck** built from real client data (branches genericized to "Branch 1..N", client id 999) —
no longer education-slides-only, so it's a true visual reference like the ARS/MRPC templates.
`build_ics_gen.py` now selects its static education/Q&A slides **by title** from the template
and rebuilds everything else from data, so the populated demo cannot leak into client builds
(verified: 1676 rebuild from the new template = 28 slides, 0 FAIL, no demo leakage).
E-Learning Library Guide text set explicitly to 26/20 pt (paragraph-level; inherited-size runs
included). The reference deck carries the same E-Learning update (applied after it was unlocked).

**2026-07-24 v5:** `ars_template.pptx` re-baked as a **fully self-consistent Union
Financial demo built from real client data (Sugar River 1038)** — 47 slides incl. Product Mix,
Contact, all current chart styles (unified swipes/NSF axes, taller charts, fixed Reg E stacks).
`build_ars_gen.py`'s 109 find-strings were mechanically rewritten to the new template literals
(recorded during an instrumented demo build); **equivalence proven**: a real 1038 build from the
new template is text-identical on all 47 slides to the prior known-good build, 0 FAIL.
`mrpc_template.pptx`: Tier Mix card baked into Key Metrics (was an empty backdrop), fixed
Retention images, Contact Us added as the final slide; MRPC builder is idempotent (won't
duplicate Contact/Tier Mix). ARS builder likewise skips Contact if baked. Gate PASS everywhere.
Remaining: the multi-product reference still carries the older Marine-era ARS section and no
Contact slide — refresh pending.

**2026-07-24 v6: reference RE-MATERIALIZED from the three demo templates.**
`multi-product_reference_deck.pptx` is now assembled from `ars_template` (base: shell + ARS
section + Q&D/Contact/Appendix) + the ICS section (divider, content, education — from
`ics_template`) + the MRPC section (divider + content — from `mrpc_template`), all Union
Financial demo data. 79 slides: Title (3 products) · Summit · combined Agenda · ARS (4–30) ·
ICS (31–53) · MRPC (54–62) · Q&D · Contact · ARS Appendix (65–79). Sequentially renumbered;
images relinked across files; hyperlinks stripped. MRPC "Austin Bank" neutralized to Union
Financial in mrpc_template + reference (safe — the MRPC builder swaps titles by position).
**Cancellations by Reason is now ranked horizontal bars** (donut+legend scaled poorly with
4–8 reasons; bars need no legend and fit any count) — renderer change, all builds get it.
The OLD section map above (67-slide Marine reference) is historical.

**2026-07-24 v7 (LATEST):** Ship-prep round. All 3 product **dividers** share one canonical
layout (logo card TL, centered 52pt title, orange benefits line — ARS line now "Mailings ·
Debit Card · Reg E" for symmetry); ICS **title slide** canonized to the ARS/MRPC layout
(centered lockup + 40pt title + orange client/review lines) in builder + template. ICS builder
now **STOPS with a clear missing-input message** on partial-data clients (null workbook
sections) instead of a raw traceback. `fit_layout` strips slide numbers from all divider/cover
slides (all programs). `mrpc_template_base.pptx` retired to archive — **one** MRPC template.
Exportable **ARS Build Package.zip regenerated** from this state and verified self-contained
(a real client build ran from inside the package, 0 FAIL; package carries its own qa baseline).
GATE PASS across all templates + built ARS/ICS/MRPC decks.