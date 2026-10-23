# Ported from ARS v5 02-Scripts/tests/test_band_table.py at a491b5c (James Gilmore); logic unchanged.
"""Band tables must label the column they actually print (#73).

Slide 27's ticket-size and intensity tables were headed 'Share' while the
cells carried raw account counts -- the share sits in the third element of
each row and was never rendered.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import txn_slides  # noqa: E402

ROWS = [["$0-10", 1200, 34.3], ["$10-25", 900, 25.7], ["$25+", 1400, 40.0]]


def test_band_table_header_names_every_column_it_prints():
    body = txn_slides._band_table("Ticket size", ROWS)
    assert body[0] == ["Ticket size", "Accounts", "Share"]


def test_band_table_prints_the_count_and_the_share():
    body = txn_slides._band_table("Ticket size", ROWS)
    assert body[1] == ["$0-10", "1,200", "34.3%"]
    assert body[3] == ["$25+", "1,400", "40.0%"]


def test_band_table_survives_a_row_without_a_share():
    """Older metric shapes carried only label and count."""
    body = txn_slides._band_table("Ticket size", [["$0-10", 1200]])
    assert body[1] == ["$0-10", "1,200", "-"]
