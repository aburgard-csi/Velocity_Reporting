"""
compat.py — run the ported v5 code under the pandas string semantics it was written for.

v5 runs pandas 2.3; this repo runs pandas 3. Pandas 3 infers a dedicated string dtype, under which
`astype(str)` keeps a missing value missing, where pandas 2 wrote the text "nan". v5's code cleans
up "nan" after `astype(str)` in many places, so under pandas 3 those rows silently drop out: the
parity check caught it on the first transaction section (1761's field 9 / field 11 counts came back
empty where v5 counted 9,261,674 blank values).

`legacy_strings()` restores pandas 2's behaviour (`future.infer_string = False`) for the duration of
a with-block, never process-wide. The cut's entry points (`ti_build.py`, `scripts/ti_parity.py`) run
everything inside it, frame loading included, since the option governs how strings are inferred
when a frame is created. Nothing else in this repo is affected: in a build, `ti_build.py` is its own
process, and in the test suite only `test_ti_*` modules get it (tests/conftest.py).
"""
import pandas as pd


def legacy_strings():
    return pd.option_context("future.infer_string", False)
