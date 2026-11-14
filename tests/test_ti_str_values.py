"""Issue #161: 1100 Rally's Transaction Intelligence build stopped with
"financial_services failed: MemoryError: Unable to allocate 8.39 GiB for an array with
shape (46941130,) and data type <U48".

The loader keeps transaction_type, merchant_key, mcc_code and the other repeated fields as
categoricals, and `Categorical.astype(str)` under pandas 2 semantics builds a fixed-width numpy
string array over every row first. `ti.compat.str_values` does the cast once per category; these
tests pin that it gives the same strings and that no TI section goes back to the old call.
"""
import pathlib
import re
import sys
import tracemalloc

import numpy as np
import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
TI = HERE.parent / "build" / "ars_pipeline"
sys.path.insert(0, str(TI))

from ti.compat import str_values  # noqa: E402


def _cat(values):
    return pd.Series(pd.Categorical(values), index=[f"r{i}" for i in range(len(values))], name="c")


@pytest.mark.parametrize("values", [
    ["sig", "PIN", None, "ach ", "sig"],
    [5411, 5812, None, 5411],
    ["only"],
    [None, None],
])
def test_same_strings_as_astype_str(values):
    s = _cat(values)
    pd.testing.assert_series_equal(str_values(s), s.astype(str))
    pd.testing.assert_series_equal(str_values(s, lambda v: v.str.upper().str.strip()),
                                   s.astype(str).str.upper().str.strip())


def test_missing_reads_nan_as_astype_str_writes_it():
    s = _cat(["a", None])
    assert list(str_values(s)) == ["a", "nan"]
    assert list(str_values(s, lambda v: v.str.upper())) == ["A", "NAN"]


def test_plain_column_falls_back_to_astype_str():
    s = pd.Series(["x", None, "y"], dtype=object)
    pd.testing.assert_series_equal(str_values(s), s.astype(str))


def test_filtered_rows_keep_their_index():
    s = _cat(["a", "b", "a", "c"])
    mask = pd.Series([True, False, True, True], index=s.index)
    pd.testing.assert_series_equal(str_values(s)[mask], s.astype(str)[mask])


def test_financial_services_does_not_widen_every_row():
    """The failing step, on a frame shaped like the loader's. With a 100-character merchant_key
    the old cast held 400 bytes a row in one array (peak about 930 bytes a row); now about 170."""
    from ti import dictionaries
    from ti.transaction_intelligence import financial_services as F

    n = 50_000
    rng = np.random.default_rng(161)
    descs = np.array(["XX1056 PURCHASE-SIG 07/10 13:17 NETFLIX.COM HYANNIS MA 69424885 0701",
                      "VENMO PAYMENT 888888888", "CHASE CREDIT CRD CHECK PYMT 000000000006182",
                      "NATIONAL GRID vi CHECK PYMT 7017"], dtype=object)
    df = pd.DataFrame({
        "transaction_date": pd.Timestamp("2026-07-01") + pd.to_timedelta(rng.integers(0, 28, n), unit="D"),
        "primary_account_num": pd.Series(rng.integers(0, 500, n)).astype(str).to_numpy(dtype=object),
        "transaction_type": pd.Categorical(rng.choice(["SIG", "PIN", "ACH"], n)),
        "amount": rng.random(n) * 100,
        "merchant_name": descs[rng.integers(0, 4, n)]})
    df["merchant_key"] = pd.Categorical(np.where(rng.random(n) < .5, "K" * 100, "SHORT"))
    spec = F.load_patterns(dictionaries.folder(), None)

    tracemalloc.start()
    try:
        base = tracemalloc.get_traced_memory()[0]
        rows = F.classify_rows(df, spec)
        F.compute(df, None, spec, pd.Timestamp("2026-07-31"), None, lambda _m: None, classification=rows)
        peak = tracemalloc.get_traced_memory()[1] - base
    finally:
        tracemalloc.stop()
    assert peak / n < 400, f"financial_services peaked at {peak / n:.0f} bytes a row"


CATEGORICAL = "transaction_type|merchant_key|mcc_code|merchant_id|card_present|source_file"
OLD_CALL = re.compile(r'\[(?:\w+\s*,\s*)?"(?:' + CATEGORICAL + r')"\]\s*\.astype\(\s*str\s*\)')


def test_no_ti_section_casts_a_categorical_column_row_by_row():
    hits = []
    for path in sorted((TI / "ti").rglob("*.py")):
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if OLD_CALL.search(line):
                hits.append(f"{path.relative_to(TI)}:{no}: {line.strip()}")
    assert not hits, "use ti.compat.str_values (issue #161):\n" + "\n".join(hits)
