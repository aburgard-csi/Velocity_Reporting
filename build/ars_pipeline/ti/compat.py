"""
compat.py — run the ported v5 code under the pandas 2 behaviour it was written for.

v5 runs pandas 2.3; this repo runs pandas 3. Two differences change what the ported code computes,
and both are restored here, for the duration of a with-block, never process-wide:

  * Strings. Pandas 3 infers a dedicated string dtype, under which `astype(str)` keeps a missing
    value missing where pandas 2 wrote the text "nan". v5 cleans up "nan" after `astype(str)` in
    many places, so under pandas 3 those rows silently drop out: the parity check caught it on the
    first transaction section (1761's field 9 / field 11 counts came back empty where v5 counted
    9,261,674 blank values). Restored with `future.infer_string = False`.
  * `pd.to_datetime(None)`. Pandas 2 returns None; pandas 3 returns NaT. v5 writes
    `pd.to_datetime(df.get("Date Opened"), errors="coerce")` and then tests `is not None`, so with
    the column absent pandas 3 raised `'NaTType' object has no attribute 'notna'` where v5 skipped
    the cut (retention, 2026-10-23; 24 call sites in v5). Restored by answering None for None.

The cut's entry points (`ti_build.py`, `scripts/ti_parity.py`) run everything inside
`legacy_strings()`, frame loading included, and only `test_ti_*` tests get it (tests/conftest.py).
In a build `ti_build.py` is its own process, so nothing of Aaron's ever runs under it.
"""
import contextlib

import pandas as pd


@contextlib.contextmanager
def legacy_strings():
    original = pd.to_datetime

    def to_datetime(arg, *args, **kwargs):
        return None if arg is None else original(arg, *args, **kwargs)

    with pd.option_context("future.infer_string", False):
        pd.to_datetime = to_datetime
        try:
            yield
        finally:
            pd.to_datetime = original
