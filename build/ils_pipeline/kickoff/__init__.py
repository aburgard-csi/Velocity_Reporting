"""ILS kickoff: v5 `02-Scripts/ils/kickoff_analysis/` at 7ba1e63, ported (a proposal).

The loader (`core/io.py`), the eight analyses (`metrics/`), the run (`run.py`) with its 19-tab
workbook (`deck/report.py`, `deck/charts.py`), and the deck (`deck/slides.py`, `deck/forms.py`).
`_v5/` holds kickoff's copies of the v5 helpers the deck draws through (`deckkit`, `ars/deck/`,
`core/`) and the pandas 2 shim everything runs under. README.md is v5's.

Run it through `ils_pipeline/kickoff_input.run_kickoff` (two steps: the field summary, then the
confirmed codes) or `cd build; python -m ils_pipeline.kickoff.run <id> <yyyy-mm> [--deck]` (asks for
the codes at a terminal). It writes to `Build Artifacts/ils/kickoff/<id>/<period>/`, never Outputs.
"""
