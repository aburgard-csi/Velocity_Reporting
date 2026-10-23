# Ported from ARS v5 02-Scripts/tests/test_closed_account_lens.py at a491b5c (James Gilmore); logic unchanged.
"""The transaction chapter can now see a closed account.

    python -m pytest tests/test_closed_account_lens.py -q

lens.py never read Date Closed, so the chapter's population was whatever is
in today's file -- the book minus everyone who already left. attrition.py
states the law that breaks, in its own docstring, and is never called from
the chapter (#105):

    "not against accounts present in today's file, which would undercount
     by excluding everything that already left"

The lenses are ADDITIVE. No existing lens, base or headline moves; the
chapter gains the ability to ask the question. Whether its headline base
should change is a separate decision and is not taken here.
"""
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.transaction_intelligence import lens as L  # noqa: E402

ANCHOR = pd.Timestamp("2026-08-31")


def _odd(closed):
    return pd.DataFrame({
        "Acct ID": [str(i) for i in range(len(closed))],
        "Date Opened": ["2020-01-01"] * len(closed),
        "Date Closed": closed,
    })


def test_a_closed_account_is_visible():
    lenses = L.build(_odd([None, "2026-03-01", None, "2026-05-01"]),
                     ANCHOR, lambda *_: None)
    assert len(lenses.ids("closed")) == 2
    assert len(lenses.ids("still_open")) == 2


def test_the_two_lenses_partition_the_book():
    closed = [None, "2026-03-01", None, None, "2026-05-01"]
    lenses = L.build(_odd(closed), ANCHOR, lambda *_: None)
    assert (len(lenses.ids("closed")) + len(lenses.ids("still_open"))
            == len(lenses.accounts))


def test_no_date_closed_warns_and_says_what_it_costs():
    warned = []
    lenses = L.build(_odd([None, None, None]), ANCHOR, warned.append)
    assert "closed" not in lenses.masks
    assert any("already left" in w for w in warned), warned


def test_the_lenses_are_additive():
    """Every lens that existed before must still exist, unchanged."""
    odd = _odd([None, "2026-03-01", None])
    odd["Business?"] = ["N", "N", "Y"]
    lenses = L.build(odd, ANCHOR, lambda *_: None)
    for name in ("all", "business", "personal", "new_accounts"):
        assert name in lenses.masks, f"{name} was lost"
    assert len(lenses.ids("all")) == 3, "the base must not have moved"


def test_closed_is_not_a_standard_lens():
    """It is available, not imposed: the chapter's default surfaces are
    unchanged until someone chooses to use it."""
    assert "closed" not in L.STANDARD
    assert "closed" in L.EXTRA
    assert L.LABELS["closed"] == "Closed accounts"
