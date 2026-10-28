"""Kickoff's own copies of the v5 helpers it needs, and the pandas 2 shim it runs under.

`compat.py` is `build/ars_pipeline/ti/compat.py`, byte for byte: the kickoff never imports `ti`.
Every v5 file that arrives here with a later stage keeps v5's layout below this folder, so its
relative imports still hold. Kickoff's copies live here, never in `build/ils_pipeline/core/`, which
belongs to the ILS pre-go-live port.
"""
