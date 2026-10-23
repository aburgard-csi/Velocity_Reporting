# Ported from ARS v5 02-Scripts/tests/test_declining_lens.py at a491b5c (James Gilmore); logic unchanged.
"""The still-spending decliners as a lens (#245, legacy attrition_txn 08):
every section that takes a lens -- competition, finserv, merchants -- then
reports them, and the competition run writes them as a roster ranked by
balance. "Recently inactive" covered only accounts that had already gone
quiet; the group a win-back can reach is the one still spending, less.

    python -m pytest tests/test_declining_lens.py -q
"""
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.core import account_lenses as AL  # noqa: E402

TAGS = ["Mar26", "Apr26", "May26", "Jun26", "Jul26", "Aug26"]


def _frame(spend_rows, swipe_rows=None):
    data = {"Acct ID": [str(1000 + i) for i in range(len(spend_rows))],
            "Date Opened": ["2015-01-01"] * len(spend_rows)}
    for i, tag in enumerate(TAGS):
        data[f"{tag} Spend"] = [r[i] for r in spend_rows]
        if swipe_rows is not None:
            data[f"{tag} Swipes"] = [r[i] for r in swipe_rows]
    return pd.DataFrame(data)


def test_declining_is_still_spending_but_under_eight_tenths_of_its_prior():
    df = _frame([[300, 300, 300, 200, 200, 200],     # 0.67: declining
                 [300, 300, 300, 300, 300, 300],     # steady
                 [300, 300, 300, 0, 0, 0],           # gone quiet: recently_inactive, not declining
                 [0, 0, 0, 100, 100, 100]])          # new spend: not declining
    masks = AL.masks_for(df, pd.Timestamp("2026-08-31"), lambda *_: None)
    assert masks["declining"].tolist() == [True, False, False, False]
    assert AL.label("declining") == "Declining, still spending"


def test_a_swipe_collapse_on_steady_spend_is_declining_too():
    df = _frame([[300] * 6, [300] * 6], [[12, 12, 12, 2, 2, 2], [12] * 6])
    masks = AL.masks_for(df, pd.Timestamp("2026-08-31"), lambda *_: None)
    assert masks["declining"].tolist() == [True, False]
