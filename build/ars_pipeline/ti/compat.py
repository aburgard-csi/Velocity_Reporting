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

`str_values` is `astype(str)` on a categorical column done once per category (issue #161).
"""
import contextlib

import numpy as np
import pandas as pd


def str_values(s: pd.Series, fn=None) -> pd.Series:
    """`s.astype(str)`, then `fn` (a `.str` step such as upper or strip), row for row the same,
    without the full-width copy.

    The loader keeps transaction_type, merchant_key, mcc_code and the other repeated fields as
    categoricals. Under pandas 2 semantics `Categorical.astype(str)` first builds a fixed-width
    numpy string array over EVERY row (4 bytes x the longest value x rows) and only then boxes it:
    1100 Rally's 46,941,130 rows of merchant_key asked for 8.39 GiB at once and the build stopped
    with a MemoryError in financial_services (James Gilmore, 2026-11-13, issue #161). Here the
    categories are cast (and `fn` run) once each, a missing value becoming "nan" exactly as
    astype(str) writes it, and every row points at its category's string.
    """
    if isinstance(s.dtype, pd.CategoricalDtype) and not pd.get_option("future.infer_string"):
        cats = np.asarray(s.cat.categories.astype(str), dtype=object)
        vals = pd.Series(np.append(cats, "nan"), dtype=object)      # code -1 (missing) -> "nan"
        if fn is not None:
            vals = fn(vals)
        vals = np.asarray(vals, dtype=object)
        return pd.Series(vals[s.cat.codes.to_numpy()], index=s.index, name=s.name, dtype=object)
    out = s.astype(str)
    return fn(out) if fn is not None else out


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
