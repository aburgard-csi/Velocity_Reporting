# Ported from ARS v5 02-Scripts/tests/test_tables.py at a491b5c (James Gilmore); logic unchanged.
"""The analyst table layer: every declared table as a CSV.

    python -m pytest tests/test_ti_tables.py -q

The legacy printed 41 data frames. They never reached a deck but they were
the working surface -- where you check a number, or answer a question the
slides did not anticipate. v5 went from raw file to finished slides with
nothing in between.

The layer is mechanical on purpose: declare `<key>_columns` and your table
appears, so new analysis is readable the day it is computed. The tests below
pin that, and pin the two ways a mechanical writer can lie -- headers sliding
out of line with their data, and tables disappearing without a word.
"""
import csv
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.monthly_analysis import tables  # noqa: E402


def _write(metrics, tmp_path):
    warnings = []
    written = tables.write(metrics, tmp_path, warnings.append)
    return written, warnings


def _read(path):
    # utf-8-sig, as any correct reader of these files must be -- they carry a
    # BOM so Excel on Windows decodes them properly.
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.reader(fh))


def test_a_metric_that_declares_its_columns_is_written(tmp_path):
    metrics = {"thing_by_branch": [["Main", 10, 1.5], ["Harbor", 20, 2.5]],
               "thing_by_branch_columns": ["branch", "n", "rate"]}
    written, _ = _write(metrics, tmp_path)

    rows = _read(written["thing_by_branch"])
    assert rows[0] == ["branch", "n", "rate"]
    assert rows[1] == ["Main", "10", "1.5"]
    assert len(rows) == 3


def test_a_table_without_columns_is_skipped_and_named(tmp_path):
    """Silently dropping it would read as 'that section produced nothing'."""
    metrics = {"mystery": [[1, 2], [3, 4]]}
    written, warnings = _write(metrics, tmp_path)

    assert written == {}
    assert any("declare no columns" in w and "mystery" in w
               for w in warnings), warnings


def test_known_legacy_tables_are_written_without_a_columns_key(tmp_path):
    """The tables that predate the convention still reach the analyst."""
    metrics = {"campaign_rates": [["Apr26", 18735, 2093, 11.2]]}
    written, _ = _write(metrics, tmp_path)

    rows = _read(written["campaign_rates"])
    assert rows[0] == ["wave", "mailed", "responded", "rate_pct"]
    assert rows[1][1] == "18735"


def test_headers_never_slide_left_of_their_data(tmp_path):
    """A row wider than its declared header is the one way a mechanical
    writer produces a plausible, wrong table."""
    metrics = {"wide": [["a", 1, 2, 3]], "wide_columns": ["name", "x"]}
    written, _ = _write(metrics, tmp_path)

    rows = _read(written["wide"])
    assert len(rows[0]) == len(rows[1]) == 4
    assert rows[0][:2] == ["name", "x"]
    assert rows[0][2:] == ["col3", "col4"]


def test_scalars_and_dicts_are_not_mistaken_for_tables(tmp_path):
    metrics = {"a_number": 42, "a_dict": {"x": 1}, "a_list": [1, 2, 3],
               "a_string": "hello", "empty": []}
    written, _ = _write(metrics, tmp_path)
    assert written == {}


def test_nothing_is_recomputed_on_the_way_out(tmp_path):
    """A CSV must never disagree with the slide built from the same key, so
    values pass through exactly as the metric holds them."""
    metrics = {"t": [["x", 0.30000000000000004, None, 1200]],
               "t_columns": ["a", "b", "c", "d"]}
    written, _ = _write(metrics, tmp_path)

    row = _read(written["t"])[1]
    assert row[0] == "x"
    assert row[1] == "0.30000000000000004"
    assert row[2] == ""
    assert row[3] == "1200"


def test_the_run_is_told_how_many_tables_landed(tmp_path):
    metrics = {"t": [[1]], "t_columns": ["a"]}
    _written, warnings = _write(metrics, tmp_path)
    assert any("table(s) written" in w for w in warnings), warnings


def test_no_directory_is_created_when_there_is_nothing_to_write(tmp_path):
    _write({"a_number": 1}, tmp_path)
    assert not (tmp_path / "tables").exists()


def test_csvs_open_cleanly_in_excel_on_windows(tmp_path):
    """These files exist to be read by a person on a Windows machine.

    Without a BOM Excel decodes UTF-8 as the local code page and every
    accented merchant or institution name garbles -- the repo's config reader
    already uses utf-8-sig for the same reason.
    """
    metrics = {"t": [["Peña Bank", 10], ["Crédit Mutuel", 20]],
               "t_columns": ["institution", "accounts"]}
    written, _ = _write(metrics, tmp_path)
    raw = pathlib.Path(written["t"]).read_bytes()

    assert raw.startswith(b"\xef\xbb\xbf"), "no BOM: Excel will mangle this"
    text = raw.decode("utf-8-sig")
    assert "Peña Bank" in text and "Crédit Mutuel" in text
    # and it still round-trips through a plain reader
    rows = _read(written["t"])
    assert rows[0][0] == "institution", "the BOM leaked into the first header"
    assert rows[1][0] == "Peña Bank"


def test_line_endings_are_not_doubled(tmp_path):
    """csv.writer emits \\r\\n itself; without newline="" Windows would add
    a second one and every other row would be blank."""
    metrics = {"t": [["a"], ["b"]], "t_columns": ["x"]}
    written, _ = _write(metrics, tmp_path)
    raw = pathlib.Path(written["t"]).read_bytes()
    assert b"\r\r\n" not in raw, "line endings doubled"
    assert raw.count(b"\n") == 3
