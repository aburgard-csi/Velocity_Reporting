# build/ — deck assembly machinery

Requires `python-pptx`, `matplotlib`, `openpyxl`, `Pillow` (and `pyarrow` for `metrics_gen`).
Every deck is BUILT from its program's shell in `templates/` (`ars_template.pptx`,
`ics_template.pptx`, `mrpc_template.pptx`); no deck is cloned from a client deck
(CLAUDE.md "Templates"). CashPlease (`C:\Projects\CashPlease`, staged to move here)
builds onto `ars_template.pptx` as a bare shell and imports the shared layer below.

## Current layout (reorganized 2026-07-24)

One folder per program; shared post-processors at the root.

- **`ars_pipeline/`** — the complete, client-agnostic ARS chain:
  `build_ars_gen.py` (the assembler) plus `metrics_gen.py`, `charts_gen.py`,
  `extract_base_gen.py`, `extract_lift.py`, `render_lift.py`, `ticket_calc.py`,
  `ticket_chart.py`, `base_tab_extract.py` (SM financials), `product_mix_slide.py`.
  `build_ars_gen.py` self-locates its helpers (`REF` = this dir; `BUILDDIR` = `build/`),
  overridable with `RPE_REF` / `RPE_BUILDDIR`.
- **`ics_pipeline/`** — `build_ics_gen.py`, `ics_charts_gen.py`, `ics_workbook_extract.py`.
  Per-client VIP data lives ONLY under `RPE_DATA_ROOT/Inputs/VIP Data/` (the repo `data/`
  copies were deleted 2026-08-29).
- **`mrpc_pipeline/`** — `build_mrpc_gen.py`, `mrpc_charts_gen.py`, `setup_template.py`
  (one-time template bootstrap).
- **root (shared, all programs)** — the style layer STYLE.md's enforcement map points at:
  `brand.py` (palette + type roles), `shapes.py` (textbox / pill / tile / table / shadow),
  `periods.py` (date phrases and the `MMM'YY` axis format), `textfit.py` (measured glyph
  widths), `slide_geometry.py` (per-title geometry contract), `fit_layout.py` (layout-fit +
  10 pt numbers), `restyle_fonts.py` (font roles + 16 pt floor, run last), `summit_slide.py`,
  `figures.py` (the provenance sidecar), `strip_dead.py` (zip-level dead-slide GC),
  `assemble_combined.py` (the combined deck), `branch_names.py`, `rpe_env.py`.

The ODD optimizer is `../scripts/oddd_optimize.py`; the pre-ship validator is
`../validation/validate_deck.py`. `metrics_gen.py` streams + column-projects the ODD `.zip`
in place (peak memory ~1.3GB; largest client ~42s).

## archive/ — retired, do not call

`../archive/` holds superseded code (see `../archive/MANIFEST.md`): per-client one-offs,
old Marine polish scripts, the deprecated pre-`build_ars_gen` ARS recipe
(`build_gen`/`build_gen_b`/`build_swipepct`/`style_tables`/`swap_imgs`), `*_orig` backups,
a duplicate validator, and the old combined-Marine helpers. Nothing in the live pipelines
references it; restore with a move-back if ever needed.

---

## ARS SM vs MM revenue models (base_tab_extract.py)

**SM vs MM are two ARS revenue-calculation models, not broken-vs-working:**
- **MM model** (lift-matrix): revenue in the month-end "MM" tabs. Marine, FNBT. Standard pipeline reads MM tabs.
- **SM model** (split **Interchange + NSF**, computed on the individual mailing tabs): older clients. Sugar River 1038. Its MM tabs are legitimately blank — expected, not a defect, nothing to report to the data team.

Detect: if `Executive Financials MM!B4 == "Bank Name"` (or header month is 2007/2008), it's an SM-model workbook → use this extractor.

Reads the SM/base tabs and normalizes to standard figures:
- **Executive Financials**: client, data month, months, mailings, current+LTD revenue/profit/costs, profitability (=LTD rev / |LTD costs|).
- **All Months Rollup**: monthly incremental revenue = `Total Interchange Revenue` + `Total NSF Revenue` rows (the SM split — ties to Exec Financials exactly). NOT the "Marginal Increase in Debit Spend" rows (that's spend). Trailing-12 series + sum + avg.
- **Key Trends**: Total Spend (millions); card-holding = Total Accounts − Non Card Holding (×1000); 36-mo tail for the swipes/spend combo.
- **Mail Response Summary**: rows are OLDEST-first with a descending index; newest 12 = `reversed(rows[-12:])`. Columns: NU5+ response, Threshold-met.
- **DCO file** (2nd arg): Eligible ARS Accounts.

Take-rate / Reg E / appendix still come from the ODD (same as the MM pipeline). SM clients have no lift-matrix slide.

Usage: `python3 base_tab_extract.py <workbook.xlsx> [<dco.xlsx>]`
