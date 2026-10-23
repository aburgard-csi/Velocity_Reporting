# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/txn_common.py at a491b5c (James Gilmore); logic unchanged.


def ranked(counts, ascending: bool = False):
    """A ranking whose ties break the same way on every machine.

    pandas' default sort is quicksort, which is NOT stable, so rows with equal
    counts come out in an arbitrary order that differs between platforms and
    numpy versions. On the work PC that made three metric keys disagree with
    the same run on macOS -- SHELL and UBER both on 798 accounts, AMEX and
    FIDELITY both on 1,969 transactions -- which means a deck could name a
    different "top merchant" for identical data.

    Sorting the index first and then sorting by value with a STABLE kind
    breaks every tie alphabetically, which is both reproducible and defensible
    on a slide.
    """
    return counts.sort_index().sort_values(ascending=ascending, kind="mergesort")
