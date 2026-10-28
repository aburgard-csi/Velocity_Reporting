"""ILS kickoff: v5 `02-Scripts/ils/kickoff_analysis/`, ported one stage per branch.

v5's package has `run.py`, `metrics/` and `deck/`; each arrives with its own stage. Here so far: the
loader (`core/io.py`), the eight analyses (`metrics/`), and the run (`run.py`) with the 19-tab
workbook it writes (`deck/report.py`, `deck/charts.py`). The deck slides arrive with the next stage.
`_v5/` holds kickoff's copies of the v5 helpers it needs and the pandas 2 shim it runs under.

Run it through `ils_pipeline/kickoff_input.run_kickoff` (two steps: the field summary, then the
confirmed codes) or `cd build; python -m ils_pipeline.kickoff.run <id> <yyyy-mm>` (asks for the
codes at a terminal). It writes to `Build Artifacts/ils/kickoff/<id>/<period>/`, never to Outputs.
"""
