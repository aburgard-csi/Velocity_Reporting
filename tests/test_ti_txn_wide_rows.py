# Ported from ARS v5 02-Scripts/tests/test_txn_wide_rows.py at a491b5c (James Gilmore); logic unchanged.
# Left out: test_the_report_says_read_short_at_the_top (v5's text report, not ported).
"""A file whose rows get wider partway must still be read to the end (#256).

On RALLY 1100 nine of eleven "combined" transaction files parsed to exactly
1,500,004 rows from 4.8 to 5.5 million lines, from source, with the quote fix
in place. The only fault that stops pandas' C parser silently at a fixed row
is every line from that row on carrying MORE fields than the first row: each
is a "bad line", on_bad_lines="skip" drops it, and the parse ends where the
widening began. A file stitched from two extracts, the second with an extra
column or a trailing tab, has exactly that shape.

    python -m pytest tests/test_txn_wide_rows.py -q
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.transaction_intelligence import loader  # noqa: E402

BANNER = "1100|8/5/2026 3:44:20 PM|Jul 2026|507|Monthly Transaction File|6.0.8.0"
ACCT = "554057DB9EF15CC6C3F56A8628FF048B4EAE3620"
ROWS, AT = 60, 20


def _row(i, extra=""):
    return (f"07/{1 + i % 28:02d}/2026\t{ACCT}\tPIN\t{10 + i}.50\t5411\t"
            f"MERCHANT {i}\tMCALLEN\tTXUS\t\t3090\t\t60{extra}")


def _write(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="latin-1")


def _read(path):
    rpt = loader.LoadReport()
    frame = loader.read_file(path, path.parent / "_cache", rpt)
    return frame, rpt


def test_rows_that_widen_partway_are_all_read(tmp_path):
    """The 1100 shape: an extra column from a fixed row to the end."""
    raw = tmp_path / "1100_507_combined transaction_8-5-26.txt"
    _write(raw, [BANNER] + [_row(i) for i in range(AT)]
           + [_row(i, "\tEXTRA") for i in range(AT, ROWS)])
    frame, rpt = _read(raw)
    assert len(frame) == ROWS, "the parse stopped where the rows widened"
    assert frame["amount"].notna().all()
    assert not [w for w in rpt.warnings if "READ SHORT" in w]
    assert any("wider" in w for w in rpt.warnings), rpt.warnings


def test_a_trailing_tab_from_a_fixed_row_is_all_read(tmp_path):
    raw = tmp_path / "1100_507_combined transaction_8-5-26.txt"
    _write(raw, [BANNER] + [_row(i) for i in range(AT)]
           + [_row(i, "\t") for i in range(AT, ROWS)])
    frame, _ = _read(raw)
    assert len(frame) == ROWS


def test_a_second_banner_mid_file_costs_only_its_own_line(tmp_path):
    raw = tmp_path / "1100_507_combined transaction_8-5-26.txt"
    _write(raw, [BANNER] + [_row(i) for i in range(AT)] + [BANNER]
           + [_row(i, "\tEXTRA") for i in range(AT, ROWS)])
    frame, _ = _read(raw)
    dated = frame[frame["transaction_date"].notna()]
    assert len(dated) == ROWS


def test_a_short_read_is_never_cached(tmp_path, monkeypatch):
    """If a parse still comes up short, the next run must re-read the file,
    not serve the short frame as if it were the file."""
    raw = tmp_path / "1100_507_combined transaction_8-5-26.txt"
    _write(raw, [BANNER] + [_row(i) for i in range(ROWS)])
    monkeypatch.setattr(loader, "is_short", lambda rows, lines, skip=0: True)
    _, rpt = _read(raw)
    assert any("READ SHORT" in w for w in rpt.warnings)
    assert not list((tmp_path / "_cache").glob("*.parquet"))
