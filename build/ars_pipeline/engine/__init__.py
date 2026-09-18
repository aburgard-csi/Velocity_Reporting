"""The ARS analysis engine, ported from James Gilmore's v5 platform (2026-09-18).

One package, relative imports throughout. `core/` is the ODD transform, the subset layer
(every denominator built once), account facts and named conditions; `monthly_analysis/` is
the section registry (`metrics.SECTIONS`) and the sections; `transaction_intelligence/`
reads the monthly debit transaction files; `text/` turns metrics into sentences; `config/`
carries the dictionaries the transaction sections classify against.

Every classification the deck also makes (eligibility, debit, business, Reg E, the ODD zip
member) is read through `odd_rows`, the one place those rules live. Nothing here writes a
slide: the seam to the deck is metrics.json and txn_metrics.json, written by
`build/ars_pipeline/run_analysis.py`.

Not ported in this branch: ICS behaviour views, the deposits file, the market scan, ILS,
CashPlease, the v5 deck (`ars/deck`) and lab. See CHANGELOG.md.
"""
