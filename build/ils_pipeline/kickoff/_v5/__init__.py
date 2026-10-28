"""Kickoff's own copies of the v5 helpers it needs, and the pandas 2 shim it runs under.

`compat.py` is `build/ars_pipeline/ti/compat.py`, byte for byte: the kickoff never imports `ti`.

The rest is v5 at 7ba1e63, laid out as in v5's `02-Scripts/` so its relative imports still hold:
`deckkit/` (the product-neutral deck facade the kickoff deck draws through), `ars/deck/` (what that
facade re-exports, and every module `ars/deck/build.py` imports at load), and `core/` (`layout.py`
for the template, plus what `core/__init__.py` and `ars/deck/deposit_slides.py` import). Absolute
imports are rewritten to this package; nothing else is edited. Imported lazily by v5 and never
reached by the kickoff, so not copied: `ars/deck/ics_slides.py` and `ars/core/env.py` (from
`ars.deck.build.build`, the ARS deck) and `core/env.py` (from `core.result`, when a result is saved).

Kickoff's copies live here, never in `build/ils_pipeline/core/`, which belongs to the ILS pre-go-live
port.
"""
