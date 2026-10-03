"""A stray quote must not swallow the file (issue #179, RALLY 1100).

These extracts do not quote fields. Under pandas' default QUOTE_MINIMAL a `"`
at the start of a field opens a quoted value and every line up to the NEXT `"`
anywhere in the file is absorbed into it. On 1100 that turned 5,533,493 lines
into 1,500,004 rows, with no warning: a swallow is not a bad line, so
on_bad_lines="skip" never sees it, and the row count is the only evidence.

    python -m pytest tests/test_txn_quote_swallow.py -q
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "build" / "ars_pipeline"), str(HERE.parent / "build")]

from engine.transaction_intelligence import loader  # noqa: E402

BANNER = "1100|6/8/2026 3:44:20 PM|May 2026|507|Monthly Transaction File|6.0.8.0"
ACCT = "554057DB9EF15CC6C3F56A8628FF048B4EAE3620"
ROWS = 40


def _row(i, merchant):
    return (f"05/09/2026\t{ACCT}\tPIN\t{10 + i}.50\t5411\t{merchant}\t"
            f"MCALLEN\tTXUS\t\t3090\t\t60")


def _write(path, quote_opens_at=None, quote_closes_at=None):
    lines = [BANNER]
    for i in range(ROWS):
        merchant = "WAL-MART #6098"
        if i == quote_opens_at:
            merchant = '"WAL-MART 24 HR'
        elif i == quote_closes_at:
            merchant = 'H-E-B 12" PIZZA'
        lines.append(_row(i, merchant))
    path.write_text("\n".join(lines) + "\n", encoding="latin-1")


def _read(tmp_path, name="1100_507_combined transaction_6-9-26.txt", **kw):
    raw = tmp_path / name
    _write(raw, **kw)
    return loader.read_file(raw, tmp_path / "_cache", loader.LoadReport())


def test_a_quote_pair_does_not_swallow_the_lines_between_them(tmp_path):
    """The 1100 defect exactly: 5.5m lines in, 1.5m rows out, silently."""
    frame = _read(tmp_path, quote_opens_at=10, quote_closes_at=30)
    assert len(frame) == ROWS, "rows between two quotes were swallowed"


def test_an_unclosed_quote_does_not_kill_the_read(tmp_path):
    """Unbalanced to EOF raises ParserError under QUOTE_MINIMAL."""
    frame = _read(tmp_path, quote_opens_at=10)
    assert len(frame) == ROWS


def test_the_quote_survives_in_the_merchant_name(tmp_path):
    """Reading literally must not silently rewrite the merchant."""
    frame = _read(tmp_path, quote_opens_at=10, quote_closes_at=30)
    assert '"WAL-MART 24 HR' in frame["merchant_name"].tolist()


def test_a_clean_file_is_unchanged_by_the_quoting_rule(tmp_path):
    frame = _read(tmp_path)
    assert len(frame) == ROWS
    assert frame["transaction_date"].notna().all()
    assert frame["amount"].iloc[0] == 10.50
