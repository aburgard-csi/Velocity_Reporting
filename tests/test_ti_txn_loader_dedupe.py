# Ported from ARS v5 02-Scripts/tests/test_txn_loader_dedupe.py at a491b5c (James Gilmore); logic unchanged; the folders are
# passed to discover directly (RPE stages them, ti/txn_stage.py).
"""During the migration window a txn file can sit in BOTH layouts -- it must
load exactly once, with a warning naming the duplicate.

Canonical is now Txn Files/{client} (#109): TXN accumulates per client, so
filing by fetch-month scattered one history across folders and let the same
file arrive twice. The month-filed copies are the #12 shape, still read."""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.transaction_intelligence import loader  # noqa: E402


def test_same_file_in_both_layouts_loads_once(tmp_path):
    name = "1615_31004_[2026.08.05][07.15.50]_monthly_transactions_file_(debit).txt"
    new = tmp_path / "TXN" / "2026-08" / "1615"
    old = tmp_path / "Txn Files" / "1615"
    new.mkdir(parents=True); old.mkdir(parents=True)
    (new / name).write_text("month-filed leftover")
    (old / name).write_text("canonical")
    (old / "1615_31004_[2026.07.05][07.00.00]_monthly_transactions_file_(debit).txt") \
        .write_text("july, legacy only")

    # RPE: find_txn_dirs points at ti/txn_stage.py; the two folders are passed in v5's order
    dirs = [old, new]
    rpt = loader.LoadReport()
    files = loader.discover(dirs, months=12, anchor=None, rpt=rpt)

    names = [f.name for f in files]
    assert names.count(name) == 1                      # loaded once
    aug = [f for f in files if f.name == name][0]
    assert aug.read_text() == "canonical"              # the first folder given wins
    assert len(files) == 2                             # july still included
    assert any("both the new TXN layout" in w for w in rpt.warnings)
