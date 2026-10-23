# Ported from ARS v5 02-Scripts/tests/test_coverage_note.py at a491b5c (James Gilmore); logic unchanged.
# Left out: the two scorecard tests (v5's deck/build.py, not part of the cut). The slide source is
# read from ti/deck/txn_compete.py.
"""One primitive for 'this list is capped' (#71).

Three slides promised more than they rendered: a headline counting 12 lists
over 10 rows, a top-15 statistic over 10 bars, a chip count over fewer chips.
Silent truncation reads as completeness.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import labels  # noqa: E402


def test_note_appears_when_rows_are_dropped():
    assert labels.coverage_note(10, 12, "lists") == "showing 10 of 12 lists"


def test_no_note_when_everything_renders():
    assert labels.coverage_note(12, 12, "lists") is None


def test_no_note_when_the_cap_never_bit():
    assert labels.coverage_note(8, 8, "merchants") is None


def test_singular_total_still_reads():
    assert labels.coverage_note(1, 3, "branch") == "showing 1 of 3 branch"


def test_thousands_are_grouped():
    assert labels.coverage_note(20, 1500, "accounts") == "showing 20 of 1,500 accounts"


def test_the_institutions_note_counts_every_institution_that_matched():
    """comp_institutions is already cut to TOP_INSTITUTIONS (25) before the
    slide takes its top 9. Counting the note against the cut list hid the
    first cut entirely: a client with 82 configured competitors and 40
    matching read as "showing 9 of 25"."""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / "build" / "ars_pipeline"
           / "ti" / "deck" / "txn_compete.py").read_text(encoding="utf-8")
    assert 'comp_institutions_n' in src, (
        "the note must count against the matched total, not the truncated list")
    assert 'labels.coverage_note(len(rows), matched, "institutions")' in src


def test_coverage_note_is_silent_when_nothing_was_dropped():
    from ti.deck import labels
    assert labels.coverage_note(25, 25, "institutions") is None
    assert labels.coverage_note(9, 40, "institutions") == "showing 9 of 40 institutions"
