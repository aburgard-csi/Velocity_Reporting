# Deck Templates

**Every deck is BUILT by its builder from the stripped shell in this folder. No deck
is ever cloned from another client's finished deck** (Aaron, 2026-08-29 — `CLAUDE.md`
"Templates"). If a slide is wrong, fix the builder or the shell and rebuild; do not
hand-edit a deck.

## The shells

| File | Program | Slides | What it holds |
| --- | --- | --- | --- |
| `ars_template.pptx` | ARS — `build/ars_pipeline/build_ars_gen.py` argv[1] | 47 | Title · About the Summit · Agenda · ARS section (divider, Product Mix, Program Overview … ARS Key Takeaways) · Questions · Contact · Appendix (15). A self-consistent Union Financial demo built from real, neutralized data (SM path). The builder's find-strings are this file's literals; the swap gate fails on any that no longer match. |
| `ics_template.pptx` | ICS — `build/ics_pipeline/build_ics_gen.py` | 28 | Title · Summit image · divider · Agenda · content · education/reference slides · Questions · Contact. The builder selects the static education and Q&A slides **by title** and rebuilds everything else from the client JSON, so the demo cannot leak. |
| `cashplease_template.pptx` | CashPlease — `C:\Projects\CashPlease\build\build_cp_gen.py` argv[2] | 10 | Title · Summit · Agenda (one row + Questions) · divider · Program Overview · Loan Volume by Month · Loan Portfolio by Status · Peer Comparison · Questions · Contact. Materialized 2026-09-02 by running the builder on a synthetic Union Financial pack (id 999, invented figures, dummy source filename). The builder keeps the five shell slides by meaning (cover, Summit, agenda, Questions, Contact), rebuilds the five CashPlease slides from the pack, and strips the rest with `build/strip_dead.py`. |
| `mrpc_template.pptx` | MRPC — `build/mrpc_pipeline/build_mrpc_gen.py` | 12 | Title · divider · eight content slides · Questions · Contact. No agenda and no Summit slide — the builder inserts the Summit, and this is why MRPC is last in `assemble_combined.BASE_PRECEDENCE`. |
| `multi-product_reference_deck.pptx` | none — a STYLING reference | 79 | Title (three products) · Summit · combined Agenda · ARS 4–30 · ICS 31–53 · MRPC 54–62 · Questions · Contact · ARS Appendix 65–79. The source for re-materializing the three shells. **No build reads it.** |

Each shell carries the "Union Financial" dummy client (id 999, branches "Branch
1..N") — no real client's numbers, captions, branch names or speaker notes.
`validation/qa_all.py` lints every shell on every run and diffs each slide's layout
against `validation/layout_baseline.json`; an intentional change is accepted with
`--snapshot`.

**The one family without a shell.** The **ILS review prep slides** start from a
blank python-pptx presentation and are drawn entirely by the `ils-prep-deck` skill's
helpers, because they are inserted into the consultant's `.pptm` and inherit that
deck's masters.

**Re-materializing the CashPlease shell.** Run the builder on a synthetic pack for
client 999 "Union Financial" (no real client's figures or source filename) against
the current shell, and save the 10-slide result here. Any shell with the five
meaning-resolved slides works as the input, so the shell can rebuild itself.

## Swap targets

What changes per client: client name and id, the period labels and pills, every
headline figure and table value, chart images, branch names and counts, and every
source line in the notes (ODD filename + pull stamp for ARS; workbook / VIP
references for ICS, MRPC and CashPlease). Everything else — layout, colors,
dividers, education slides — stays as the shell has it.

## Maintaining the shells

- Shells are updated **in place**; the files here are always the latest. Keep a
  rollback copy under the Drive `archive/` if one is needed — not in the repo.
- To rebuild a shell, trim `multi-product_reference_deck.pptx` to that program's
  section plus the shared shell and save it under the program's name. Update the
  reference first whenever the canonical look changes, then re-materialize.
- After any shell change: run `validation/qa_all.py`, review the DRIFT lines, then
  `--snapshot`. Post the change to `CHANGELOG.md` if a slide renders differently.
- `templates/STYLE.md` is the style contract these shells embody; the per-slide
  geometry that builders enforce on top of them is `build/slide_geometry.py`.

## Version log

| Date | Change |
| --- | --- |
| 2026-07-24 v7 | One canonical divider layout on all three shells; ICS title slide canonized; ICS builder stops with a clear message on null workbook sections; `fit_layout` strips numbers from all dividers and covers; single MRPC template. |
| 2026-07-24 v6 | Reference deck re-materialized from the three demo shells (79 slides, Union Financial throughout); Cancellations by Reason as ranked bars. |
| 2026-07-24 v5 | ARS shell re-baked as a self-consistent demo from neutralized Sugar River data (47 slides); builder find-strings rewritten to its literals, equivalence proven text-identical on all slides; MRPC Tier Mix and Contact baked in. |
| 2026-07-24 v4 | ICS shell became a full 28-slide demo deck; static slides selected by title. |
| 2026-07-24 v3 | Transaction Increase chart centered; MRPC Card Portfolio donut enlarged; placeholder prompt boxes stripped. |
| 2026-07-24 v2 | Per-slide geometry contract; caption breathing room and collision validation; Union Financial neutralization. |
| ≤ 2026-07-17 v1 | Marine-derived originals, pre-QA. |
