"""ILS kickoff: v5 `02-Scripts/ils/kickoff_analysis/`, ported one stage per branch.

v5's package has `run.py`, `metrics/` and `deck/`; each arrives with its own stage. Here so far: the
loader (`core/io.py`) and the eight analyses (`metrics/`), which compute tables and write nothing.
`_v5/` holds kickoff's copies of the v5 helpers it needs and the pandas 2 shim it runs under.
"""
